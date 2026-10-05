"""Agent asset pipeline regressions. Run: python3 -m unittest discover -s tests -p test_assetkit.py

Geometry and CLI tests need only Python. Native render tests run when meic and
mei-headless have been built; `make test-assets` ensures they are available.
"""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MEIC',ROOT/'build/meic')).resolve()
RUNNER = Path(os.environ.get('RUN',ROOT/'build/mei-headless')).resolve()
PROBE = Path(os.environ.get('PROBE',ROOT/'build/mei-asset-probe')).resolve()
sys.path.insert(0,str(ROOT/'tools'))
from assetkit.compiler import compile_recipe, native_bytes, import_obj, obj_text, material_manifest
from assetkit.geometry import AssetError, cross, dot, sub
from assetkit.schema import SCHEMA, validate
from assetkit.preview import source
from mei_assets import build

PILLOW = importlib.util.find_spec('PIL') is not None
NUMPY = importlib.util.find_spec('numpy') is not None


def recipe(node=None, **extra):
    return {'format':'mei-asset','version':1,'name':'test',
            'nodes':[node or {'id':'body','op':'box','size':[2,2,2]}], **extra}


def volume(mesh):
    return sum(dot(mesh.vertices[f.indices[0]],cross(mesh.vertices[f.indices[1]],mesh.vertices[f.indices[2]]))/6 for f in mesh.faces)


class GeometryTests(unittest.TestCase):
    def test_closed_shapes_have_consistent_outward_winding(self):
        nodes = [
            {'op':'box','size':[2,3,4]},
            {'op':'sphere','radius':1},
            {'op':'cylinder','radius':1,'height':2},
            {'op':'cone','radius':1,'height':2},
            {'op':'lathe','profile':[[0,-1],[1,0],[0,1]]},
            {'op':'loft','sections':[{'y':0,'points':[[-1,-1],[1,-1],[1,1],[-1,1]]},
                                     {'y':2,'points':[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]]}]},
        ]
        for node in nodes:
            with self.subTest(node=node['op']):
                mesh,_,report = compile_recipe(recipe(node))
                self.assertGreater(volume(mesh),0)
                self.assertEqual(report['warnings'],[])

    def test_concave_extrusion_has_correct_volume_both_windings(self):
        outline = [[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]]
        for points in (outline,list(reversed(outline))):
            mesh,_,r = compile_recipe(recipe({'op':'extrude','points':points,'depth':2}))
            self.assertAlmostEqual(volume(mesh),6)
            self.assertEqual(r['triangles'],20)
            self.assertEqual(r['warnings'],[])

    def test_polygon_intersection_and_collinear_points_rejected(self):
        for points in ([[0,0],[1,1],[0,1],[1,0]], [[0,0],[1,0],[2,0],[2,1],[0,1]]):
            with self.assertRaises(AssetError):
                compile_recipe(recipe({'op':'extrude','points':points,'depth':1}))

    def test_negative_scale_preserves_outward_faces(self):
        r = recipe()
        r['nodes'][0]['transform'] = {'scale':[-1,2,3]}
        mesh,_,report = compile_recipe(r)
        self.assertAlmostEqual(volume(mesh),48)
        self.assertEqual(report['warnings'],[])

    def test_mirror_preserves_outward_faces(self):
        r = recipe({'op':'group','children':[{'op':'box','size':[1,1,1], 'transform':{'translate':[2,0,0]}}],
                    'modifiers':[{'op':'mirror','axis':'x'}]})
        mesh,_,report = compile_recipe(r)
        self.assertAlmostEqual(volume(mesh),2)
        self.assertEqual(report['bounds']['min'],[-2.5,-.5,-.5])
        self.assertEqual(report['bounds']['max'],[2.5,.5,.5])
        self.assertEqual(report['warnings'],[])

    def test_modifier_order_and_parent_transform(self):
        r = recipe({'op':'group','children':[{'op':'box','size':[1,1,1],
                    'modifiers':[{'op':'array','count':2,'step':[3,0,0]}],
                    'transform':{'translate':[1,0,0]}}], 'transform':{'scale':[2,1,1]}})
        _,_,report = compile_recipe(r)
        self.assertEqual(report['bounds']['min'],[1,-.5,-.5])
        self.assertEqual(report['bounds']['max'],[9,.5,.5])
        self.assertEqual(report['triangles'],24)

    def test_radial_taper_twist_and_subdivision(self):
        r = recipe({'op':'cylinder','radius':1,'height':2,'segments':8,
                    'modifiers':[{'op':'subdivide','levels':1},{'op':'taper','top':.6},
                                 {'op':'twist','degrees':35}]})
        _,_,report = compile_recipe(r)
        self.assertEqual(report['triangles'],112)
        self.assertEqual(report['warnings'],[])
        r = recipe({'op':'group','children':[{'op':'box','size':[1,1,1],'transform':{'translate':[2,0,0]}}],
                    'modifiers':[{'op':'radial','count':4}]})
        mesh,_,report = compile_recipe(r)
        self.assertAlmostEqual(volume(mesh),4)
        self.assertEqual(report['triangles'],48)

    def test_subdivision_conserves_shape_and_shares_edges(self):
        r = recipe()
        r['nodes'][0]['modifiers'] = [{'op':'subdivide','levels':2}]
        mesh,_,report = compile_recipe(r)
        self.assertAlmostEqual(volume(mesh),8)
        self.assertEqual(len(mesh.faces),192)
        self.assertEqual(report['warnings'],[])

    def test_fixed_point_collapsed_triangle_rejected(self):
        with self.assertRaisesRegex(AssetError,'collapses'):
            compile_recipe(recipe({'op':'box','size':[.000001,1,1]}))

    def test_coordinate_overflow_rejected(self):
        with self.assertRaisesRegex(AssetError,'16.16'):
            compile_recipe(recipe({'op':'box','size':[2,2,2],'transform':{'scale':[32767,1,1],'translate':[3,0,0]}}))

    def test_expansion_is_bounded(self):
        with self.assertRaisesRegex(AssetError,'Intermediate'):
            compile_recipe(recipe({'op':'box','size':[1,1,1],
                                   'modifiers':[{'op':'array','count':128,'step':[2,0,0]},
                                                {'op':'array','count':128,'step':[0,2,0]}]}))

    def test_budget_failure_is_actionable(self):
        with self.assertRaisesRegex(AssetError,'12 triangles; budget is 10') as error:
            compile_recipe(recipe(budget={'triangles':10}))
        self.assertEqual(error.exception.path,'/budget/triangles')

    def test_open_surfaces_are_reported(self):
        _,_,report = compile_recipe(recipe({'op':'cylinder','radius':1,'height':2,'segments':8,'caps':False}))
        self.assertEqual(report['warnings'][0]['code'],'open_surface')
        self.assertEqual(report['warnings'][0]['count'],16)

    def test_box_faces_can_be_left_out(self):
        def normals(mesh):
            out = []
            for f in mesh.faces:
                a,b,c = (mesh.vertices[i] for i in f.indices)
                n = cross(sub(b,a),sub(c,a))
                out.append(tuple(round(x/max(abs(v) for v in n)) for x in n))
            return out
        closed,_,_ = compile_recipe(recipe({'op':'box','size':[2,3,4]}))
        mesh,_,report = compile_recipe(recipe({'op':'box','size':[2,3,4],'open':['bottom']}))
        self.assertEqual(len(mesh.faces),10)
        self.assertNotIn((0,-1,0),normals(mesh))
        self.assertEqual(sorted(normals(mesh)),sorted(n for n in normals(closed) if n != (0,-1,0)))
        self.assertEqual(report['warnings'][0]['code'],'open_surface')
        # a tile: the top alone, its four corners only
        mesh,_,_ = compile_recipe(recipe({'op':'box','size':[4,0.1,4],'open':['bottom','left','right','back','front'],
                                          'transform':{'translate':[0,-0.05,0]}}))
        self.assertEqual((len(mesh.faces),len(mesh.vertices)),(2,4))
        self.assertEqual(set(normals(mesh)),{(0,1,0)})
        self.assertTrue(all(abs(v[1]) < 1e-9 for v in mesh.vertices))
        for side,n in (('top',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0)),('back',(0,0,-1)),('front',(0,0,1))):
            mesh,_,_ = compile_recipe(recipe({'op':'box','size':[1,1,1],'open':[side]}))
            self.assertNotIn(n,normals(mesh),side)
            self.assertEqual(len(mesh.faces),10)
        for value,message in ((['bottom','bottom'],'once'),([],'1–5'),(['top','bottom','left','right','back','front'],'1–5'),
                              (['under'],'one of')):
            with self.subTest(value=value),self.assertRaisesRegex(AssetError,message) as error:
                compile_recipe(recipe({'op':'box','size':[1,1,1],'open':value}))
            self.assertEqual(error.exception.path,'/nodes/0/open' + ('/0' if value == ['under'] else ''))

    def test_duplicate_faces_are_reported(self):
        r = recipe({'op':'box','size':[1,1,1],'modifiers':[{'op':'array','count':2,'step':[0,0,0]}]})
        _,_,report = compile_recipe(r)
        self.assertIn('duplicate_faces',[w['code'] for w in report['warnings']])

    def test_nonplanar_polygon_rejected(self):
        with self.assertRaisesRegex(AssetError,'not planar'):
            compile_recipe(recipe({'op':'mesh','vertices':[[0,0,0],[1,0,0],[1,1,.1],[0,1,0]],'faces':[[0,1,2,3]]}))


class ContractTests(unittest.TestCase):
    def test_polygon_materials_survive_triangulation_and_modifiers(self):
        r = recipe({'op':'mesh','vertices':[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[2,0,0],[2,1,0]],
                    'faces':[[0,1,2,3],[1,4,5,2]],'face_materials':['red','blue'],
                    'modifiers':[{'op':'subdivide','levels':1}]},
                   materials={'red':{'color':'#ff0000'},'blue':{'color':'#0000ff'}})
        mesh,_,_ = compile_recipe(r)
        self.assertEqual([f.material for f in mesh.faces],['red']*8+['blue']*8)
        r['nodes'][0]['face_materials'] = ['red']
        with self.assertRaisesRegex(AssetError,'one material'): compile_recipe(r)
        r['nodes'][0]['face_materials'] = ['red','missing']
        with self.assertRaises(AssetError) as error: compile_recipe(r)
        self.assertEqual(error.exception.path,'/nodes/0/face_materials/1')

    def test_schema_rejects_typo_with_json_pointer(self):
        r = recipe()
        r['nodes'][0]['segements'] = 8
        with self.assertRaises(AssetError) as error: validate(r)
        self.assertEqual(error.exception.path,'/nodes/0/segements')

    def test_bad_values_rejected_without_tracebacks(self):
        for key,value in (('size',[True,1,1]),('size',[float('nan'),1,1]),('size',[10**500,1,1]),('op',[]),('op',None)):
            r = recipe()
            r['nodes'][0][key] = value
            with self.subTest(key=key,value=str(value)[:20]), self.assertRaises(AssetError): validate(r)

    def test_unsafe_asset_names_rejected(self):
        for name in ('../escape','a/b','UPPER','name"','x\n'):
            with self.assertRaises(AssetError): validate(recipe(name=name))

    def test_instance_reference_cycle_and_duplicate_ids(self):
        r = recipe({'op':'instance','ref':'loop'},prototypes={'loop':{'op':'instance','ref':'loop'}})
        with self.assertRaisesRegex(AssetError,'cycle'): compile_recipe(r)
        r = recipe({'op':'instance','ref':'missing'})
        with self.assertRaisesRegex(AssetError,'Unknown prototype'): compile_recipe(r)
        r = recipe()
        r['nodes'] *= 2
        with self.assertRaisesRegex(AssetError,'Duplicate part'): compile_recipe(r)

    def test_instance_material_override_and_provenance(self):
        r = recipe({'id':'one','op':'instance','ref':'shape','material':'red'},
                   prototypes={'shape':{'id':'shape','op':'box','size':[1,1,1]}},
                   materials={'red':{'color':'#ff0000'}})
        mesh,_,report = compile_recipe(r)
        self.assertTrue(all(f.material == 'red' for f in mesh.faces))
        self.assertEqual(report['parts'][0]['id'],'one/shape')

    def test_missing_material_zero_light_and_zero_scale(self):
        cases = [recipe({'op':'box','size':[1,1,1],'material':'nope'}),
                 recipe(lighting={'direction':[0,0,0]}),
                 recipe({'op':'box','size':[1,1,1],'transform':{'scale':[1,0,1]}})]
        for r in cases:
            with self.assertRaises(AssetError): compile_recipe(r)

    def test_native_layout_winding_and_color(self):
        r = recipe(lighting={'bake':False},materials={'default':{'color':'#102030'}})
        mesh,mats,report = compile_recipe(r)
        binary = native_bytes(mesh,mats,r['lighting'])
        nv,nf,vo,fo,_ = struct.unpack_from('<HHIII',binary)
        self.assertEqual((nv,nf,vo,fo,len(binary)),(8,12,16,144,report['mesh_bytes']))
        flags,blend,tex,pal,*values = struct.unpack_from('<BBBB4H4I4H',binary,fo)
        self.assertEqual(values[:3],list(reversed(mesh.faces[0].indices)))
        self.assertEqual(values[4:8],[0x302010]*4)
        self.assertEqual(flags,0)

    def test_obj_negative_indices_and_round_trip(self):
        r = import_obj('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf -4 -3 -2 -1\n','panel')
        mesh,mats,report = compile_recipe(r)
        self.assertEqual(report['triangles'],2)
        again = import_obj(obj_text(mesh,mats),'again')
        new,_,_ = compile_recipe(again)
        self.assertEqual(mesh.vertices,new.vertices)
        self.assertEqual([f.indices for f in mesh.faces],[f.indices for f in new.faces])
        with self.assertRaises(AssetError): import_obj('v 0 0 0\nf 0 1 2','bad')

    def test_examples_validate_without_warnings(self):
        for path in (ROOT/'examples/assets').glob('*.asset.json'):
            if path.name == 'stall.asset.json' and not PILLOW: continue
            with self.subTest(path=path.name):
                _,_,report = compile_recipe(json.loads(path.read_text()),path.parent)
                # the stall's screens, posts and lantern are open surfaces on purpose
                allowed = {'open_surface'} if path.name == 'stall.asset.json' else set()
                self.assertEqual([w for w in report['warnings'] if w['code'] not in allowed],[])


class CLITests(unittest.TestCase):
    def run_cli(self,*args,text=None):
        result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),*args],
                                input=text,capture_output=True,text=True)
        self.assertNotIn('Traceback',result.stderr)
        return result,json.loads(result.stdout)

    def test_stdin_and_machine_readable_errors(self):
        result,report = self.run_cli('inspect','-',text=json.dumps(recipe()))
        self.assertEqual(result.returncode,0)
        self.assertEqual(report['triangles'],12)
        result,error = self.run_cli('inspect','-',text='{"name":"a","name":"b"}')
        self.assertEqual(result.returncode,1)
        self.assertIn('Duplicate JSON',error['errors'][0]['message'])

    def test_strict_rejects_open_surfaces(self):
        r = recipe({'op':'cylinder','radius':1,'height':1,'caps':False})
        result,error = self.run_cli('validate','-','--strict',text=json.dumps(r))
        self.assertEqual(result.returncode,1)
        self.assertFalse(error['ok'])

    def test_schema_is_published(self):
        result,data = self.run_cli('schema')
        self.assertEqual(result.returncode,0)
        self.assertEqual(data,SCHEMA)

    def test_invalid_cli_arguments_are_json(self):
        result,data = self.run_cli('build')
        self.assertEqual(result.returncode,1)
        self.assertEqual(data['errors'][0]['path'],'/arguments')

    def test_repeat_builds_are_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            original = {p.name:p.read_bytes() for p in Path(tmp).iterdir()}
            build(copy.deepcopy(recipe()),tmp)
            self.assertEqual(original,{p.name:p.read_bytes() for p in Path(tmp).iterdir()})

    def test_invalid_build_does_not_replace_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            path = Path(tmp)/'test.bin'
            previous = path.read_bytes()
            with self.assertRaises(AssetError): build(recipe(budget={'triangles':1}),tmp)
            self.assertEqual(path.read_bytes(),previous)

    def test_preview_failure_does_not_replace_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            previous = (Path(tmp)/'test.bin').read_bytes()
            r = recipe({'op':'box','size':[3,3,3]})
            with self.assertRaises(AssetError): build(r,tmp,True,Path(tmp)/'missing',Path(tmp)/'missing')
            self.assertEqual((Path(tmp)/'test.bin').read_bytes(),previous)

    def test_source_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'test.asset.json'
            p.write_text(json.dumps(recipe()))
            with self.assertRaisesRegex(AssetError,'overwrite'): build(recipe(),tmp,input_path=str(p))


def palette_recipe(**extra):
    """A surface box and an emissive box of the same colour, side by side, facing -Z."""
    materials = {'wall':{'color':'#c08040','palette':True,'tag':'wall'},
                 'neon':{'color':'#c08040','class':'emissive','tag':'sign'},**extra.pop('materials',{})}
    return recipe(None,**{'materials':materials,'lighting':{'mode':'vertical','ambient':.5},**extra}) | {'nodes':[
        {'id':'left','op':'box','size':[1,1,1],'material':'wall','transform':{'translate':[-1,0,0]}},
        {'id':'right','op':'box','size':[1,1,1],'material':'neon','transform':{'translate':[1,0,0]}}]}


def faces_of(binary):
    _,count,_,offset,_ = struct.unpack_from('<HHIII',binary)
    return [struct.unpack_from('<BBBB4H4I4H',binary,offset+36*i) for i in range(count)]


class MaterialExtensionTests(unittest.TestCase):
    # SHA-256 prefixes of every `build` output, recorded with the kit before palette materials,
    # vertical lighting and tags existed. Recipes using none of them must keep these exactly;
    # update a pin only for a deliberate change to that example recipe. The material manifest
    # (written for every build since) is an additional file, checked separately.
    LEGACY = {
        'robot':{'preview.akr':'4e8fee4ee73347b8','report.json':'113a80ee9870f5d1','robot.akr':'91303006a56188c3',
                 'robot.asset.json':'8d063b2e0302a54b','robot.bin':'db78e63a2817c462','robot.model.json':'2a9371a13914c418',
                 'robot.mtl':'a7c93e1572c28449','robot.obj':'cd3836530f2829ae'},
        'vessel':{'preview.akr':'d9023e1e0b6fffdc','report.json':'e2dac00c993eda51','vessel.akr':'45e8d25cc6fb1731',
                  'vessel.asset.json':'cb20d9c8d179312d','vessel.bin':'b54ae0a8d2736895','vessel.model.json':'c45972502fe5f586',
                  'vessel.mtl':'51aba9dfbec9a6e0','vessel.obj':'dab33524ab6e1ff1'},
        'cottage':{'cottage.akr':'7807fdaf0cfb4f38','cottage.asset.json':'ff67f836786c651e','cottage.bin':'343d8dc5fc953595',
                   'cottage.model.json':'89cdf3a951c5367f','cottage.mtl':'9201dadf12051bb0','cottage.obj':'72f3140be1f8e08d',
                   'preview.akr':'88d6a6337033dc29','report.json':'f1ddd6cf211a8e55'},
        'test':{'preview.akr':'d70ab8dac209b8a0','report.json':'7f8c8545259dfdc2','test.akr':'afaaec486ebceb10',
                'test.asset.json':'c524d9a758308cf4','test.bin':'1568544c40fd4c3e','test.model.json':'f92ea602281419c7',
                'test.mtl':'913848954b735d78','test.obj':'33a034107a6226f2'},
    }

    def test_legacy_recipes_build_byte_identical_outputs(self):
        import hashlib
        recipes = {name:json.loads((ROOT/f'examples/assets/{name}.asset.json').read_text()) for name in ('robot','vessel','cottage')}
        recipes['test'] = recipe(materials={'default':{'color':'#cf8753','smooth':True}},lighting={'direction':[1,1,0],'ambient':.3})
        for name,r in recipes.items():
            with self.subTest(asset=name), tempfile.TemporaryDirectory() as tmp:
                build(r,tmp)
                got = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in Path(tmp).iterdir()}
                manifest = json.loads((Path(tmp)/f'{name}.materials.json').read_text())
                del got[f'{name}.materials.json']
                self.assertEqual(got,self.LEGACY[name])
                # A legacy manifest: no palette, no tags, every material's faces.
                self.assertEqual(set(manifest),{'format','version','name','materials','tags'})
                self.assertEqual(manifest['tags'],{})
                self.assertTrue(all(m['palette_colour'] is None for m in manifest['materials'].values()))
                self.assertEqual(sum(m['triangles'] for m in manifest['materials'].values()),
                                 json.loads((Path(tmp)/'report.json').read_text())['triangles'])

    def test_palette_entries_classes_and_index_zero(self):
        r = palette_recipe()
        r['materials']['brick'] = {'color':'#C08040','palette':True}   # same colour, any case: shares wall's entry
        r['nodes'].append({'id':'third','op':'box','size':[1,1,1],'material':'brick','transform':{'translate':[0,2,0]}})
        mesh,mats,report = compile_recipe(r)
        entries = mesh.palette['entries']
        self.assertEqual([(e['class'],e['colour'],e['materials']) for e in entries],
                         [('surface',1,['brick','wall']),('emissive',2,['neon'])])
        self.assertEqual(report['palette']['entries'],2)
        self.assertEqual(report['palette']['emissive_entries'],1)
        # Seventeen surface colours span two palettes and never use index 0.
        r = recipe(materials={f'm{i}':{'color':f'#{i:02x}0000','palette':True} for i in range(17)},
                   palette_layout={'first':40})
        r['nodes'] = [{'id':f'b{i}','op':'box','size':[.5,.5,.5],'material':f'm{i}','transform':{'translate':[i,0,0]}} for i in range(17)]
        mesh,_,_ = compile_recipe(r)
        colours = [e['colour'] for e in mesh.palette['entries']]
        self.assertEqual(mesh.palette['palettes'],[40,41])
        self.assertEqual(colours,list(range(641,656))+[657,658])
        self.assertTrue(all(c%16 for c in colours))

    def test_share_false_forces_separate_entries(self):
        r = palette_recipe()
        r['materials']['brick'] = {'color':'#c08040','palette':True,'share':False}
        r['materials']['trim'] = {'color':'#c08040','palette':True,'share':False}
        for i,m in enumerate(('brick','trim')):
            r['nodes'].append({'id':m,'op':'box','size':[1,1,1],'material':m,'transform':{'translate':[0,2+2*i,0]}})
        mesh,mats,_ = compile_recipe(r)
        entries = mesh.palette['entries']
        self.assertEqual([(e['class'],e['colour'],e['materials'],e.get('separate',False)) for e in entries],
                         [('surface',1,['brick'],True),('surface',2,['trim'],True),('surface',3,['wall'],False),
                          ('emissive',4,['neon'],False)])
        manifest = material_manifest(mesh,mats,r)
        self.assertEqual([e.get('separate') for e in manifest['entries']],[True,True,None,None])
        # Without share: false the three share one entry, and the manifest says nothing new.
        for m in ('brick','trim'): del r['materials'][m]['share']
        mesh,mats,_ = compile_recipe(r)
        self.assertEqual([e['materials'] for e in mesh.palette['entries']],[['brick','trim','wall'],['neon']])
        self.assertNotIn('separate',material_manifest(mesh,mats,r)['entries'][0])
        with self.assertRaises(AssetError) as error:
            compile_recipe(palette_recipe(materials={'n':{'color':'#ffffff','share':False}}))
        self.assertEqual(error.exception.path,'/materials/n/share')

    def test_palette_face_layout_tint_and_emissive(self):
        r = palette_recipe(palette_layout={'slot':9,'row':37,'first':12})
        mesh,mats,_ = compile_recipe(r)
        faces = faces_of(native_bytes(mesh,mats,r['lighting']))
        normals = []
        for face in mesh.faces:
            a,b,c = (mesh.vertices[i] for i in face.indices)
            n = cross(sub(b,a),sub(c,a))
            normals.append(n[1]/math.sqrt(dot(n,n)))
        for face,(flags,blend,tex,pal,*values),ny in zip(mesh.faces,faces,normals):
            colours,uvs = values[4:8],values[8:12]
            self.assertEqual(flags&2,2)
            self.assertEqual(tex,9|16)
            self.assertEqual(pal,12)
            self.assertEqual(set(uvs[:3]),{(1 if face.material == 'wall' else 2)|37<<8})
            if face.material == 'neon':
                self.assertEqual(colours[:3],[0x808080]*3,'Emissive faces are never shaded.')
            else:
                t = round(128*(.5+.5*(1+ny)/2))
                self.assertEqual(colours[:3],[t|t<<8|t<<16]*3)

    def test_material_extension_errors_have_json_pointers(self):
        cases = [
            (palette_recipe(materials={'n':{'color':'#ffffff','class':'emissive','palette':False}}),'/materials/n/palette'),
            (palette_recipe(lighting={'mode':'vertical','direction':[0,1,0]}),'/lighting/direction'),
            (recipe(palette_layout={'slot':3}),'/palette_layout'),
            (palette_recipe(palette_layout={'first':255}),'/palette_layout/first'),
            (palette_recipe(palette_layout={'slot':15}),'/palette_layout/slot'),
            (palette_recipe(materials={'n':{'color':'#ffffff','class':'glow'}}),'/materials/n/class'),
            (palette_recipe(materials={'n':{'color':'#ffffff','tag':'Has Space'}}),'/materials/n/tag'),
        ]
        for r,path in cases:
            with self.subTest(path=path), self.assertRaises(AssetError) as error: compile_recipe(r)
            self.assertEqual(error.exception.path,path)

    def test_vertical_bake_survives_any_yaw(self):
        # The bake is in the asset's frame; mesh_at() later turns it about Y. A rotation-safe
        # bake gives every face the shade its world-space normal would get.
        from assetkit.compiler import shading
        r = recipe({'op':'group','children':[{'op':'box','size':[1,.5,2],'transform':{'rotate':[25,10,0]}},
                                             {'op':'sphere','radius':.6,'transform':{'translate':[0,1,0]}}]})
        mesh,_,_ = compile_recipe(r)
        normals = []
        for face in mesh.faces:
            a,b,c = (mesh.vertices[i] for i in face.indices)
            n = cross(sub(b,a),sub(c,a)); length = math.sqrt(dot(n,n))
            normals.append(tuple(x/length for x in n))
        def turn(n,yaw): return (n[0]*math.cos(yaw)+n[2]*math.sin(yaw),n[1],-n[0]*math.sin(yaw)+n[2]*math.cos(yaw))
        vertical, directional = shading({'mode':'vertical'}), shading({})
        worst = {'vertical':0,'directional':0}
        for yaw in (math.pi/4,math.pi/2,math.pi,4.0):
            for n in normals:
                worst['vertical'] = max(worst['vertical'],abs(vertical(n)-vertical(turn(n,yaw))))
                worst['directional'] = max(worst['directional'],abs(directional(n)-directional(turn(n,yaw))))
        self.assertLess(worst['vertical'],1e-9)
        self.assertGreater(worst['directional'],.3,'The directional bake is expected to depend on yaw.')
        # Tops light, walls mid, undersides dark.
        self.assertEqual([round(vertical(n),3) for n in ((0,1,0),(1,0,0),(0,-1,0))],[1,.725,.45])
        # Rebaking the asset turned by any yaw gives the same native colours face for face.
        r['lighting'] = {'mode':'vertical'}
        reference = [f[8:12] for f in faces_of(native_bytes(*compile_recipe(r)[:2],r['lighting']))]
        for yaw in (90,180,-37):
            turned = copy.deepcopy(r); turned['nodes'][0]['transform'] = {'rotate':[0,yaw,0]}
            mesh,mats,_ = compile_recipe(turned)
            colours = [f[8:12] for f in faces_of(native_bytes(mesh,mats,turned['lighting']))]
            close = all(abs((x>>s&255)-(y>>s&255)) <= 1 for a,b in zip(colours,reference) for x,y in zip(a,b) for s in (0,8,16))
            self.assertTrue(close,f'yaw {yaw}')

    def test_manifest_tags_and_import_file(self):
        r = palette_recipe()
        r['materials']['plain'] = {'color':'#203040','tag':'floor'}
        r['nodes'].append({'id':'base','op':'box','size':[3,.2,1],'material':'plain','transform':{'translate':[0,-.7,0]}})
        with tempfile.TemporaryDirectory() as tmp:
            report = build(r,tmp)
            out = Path(tmp)
            self.assertIn('test.materials.json',report['files'])
            manifest = json.loads((out/'test.materials.json').read_text())
            self.assertEqual(manifest['palette'],{'file':'test.pal','first_colour':0,'colours':16,'palettes':[0]})
            self.assertEqual(manifest['classes']['surface']['entries'],[1])
            self.assertEqual(manifest['classes']['emissive']['entries'],[2])
            self.assertEqual(manifest['tags'],{'floor':[[24,36]],'sign':[[12,24]],'wall':[[0,12]]})
            self.assertEqual(manifest['materials']['plain']['palette_colour'],None)
            self.assertEqual(report['tags'],{'floor':12,'sign':12,'wall':12})
            self.assertEqual([p['tags'] for p in report['parts']],[['floor'],['wall'],['sign']])
            pal = struct.unpack('<16H',(out/'test.pal').read_bytes())
            colour = (0xc0>>3)|(0x80>>3)<<5|(0x40>>3)<<10
            self.assertEqual(pal,(0,colour,colour)+(0,)*13)
            self.assertEqual((out/'test.swatch').read_bytes(),bytes([0x10,0x32,0x54,0x76,0x98,0xba,0xdc,0xfe]))
            akr = (out/'test.akr').read_text()
            for line in ('embed ASSET_TEST_PALETTE: u16 = "test.pal"','const ASSET_TEST_EMISSIVE = 2','fn asset_test_load() {'):
                self.assertIn(line,akr)
            self.assertIn('asset_test_load()',(out/'preview.akr').read_text())
        # Tags alone add a manifest but no palette files.
        r = recipe(materials={'default':{'color':'#ffffff','tag':'floor'}})
        with tempfile.TemporaryDirectory() as tmp:
            files = build(r,tmp)['files']
            self.assertIn('test.materials.json',files)
            self.assertNotIn('test.pal',files)

    def test_relocate_moves_entries_and_swatch(self):
        from assetkit.compiler import relocate
        mesh,mats,_ = compile_recipe(palette_recipe())
        binary = native_bytes(mesh,mats,{'mode':'vertical'})
        moved = relocate(binary,{1:16*70+3,2:16*71+9},slot=5,row=200)
        for before,after in zip(faces_of(binary),faces_of(moved)):
            colour = 16*70+3 if before[12]&255 == 1 else 16*71+9
            self.assertEqual((after[2],after[3],after[12]),(5|16,colour//16,colour%16|200<<8))
            self.assertEqual(after[4:12],before[4:12])
        with self.assertRaises(AssetError): relocate(binary,{1:16*70})

    def test_identity_mesh_accepts_only_swatch_faces(self):
        from assetkit.visibility import identity_mesh
        mesh,mats,_ = compile_recipe(palette_recipe())
        binary = native_bytes(mesh,mats,{'mode':'vertical'})
        for flags,blend,tex,pal,*values in faces_of(identity_mesh(binary)):
            self.assertEqual((flags&2,tex,pal,values[8:12]),(0,0,0,[0]*4))
        _,_,_,offset,_ = struct.unpack_from('<HHIII',binary)
        bad = bytearray(binary); struct.pack_into('<H',bad,offset+30,5)   # a second, different texel
        with self.assertRaisesRegex(AssetError,'swatch'): identity_mesh(bytes(bad))


@unittest.skipUnless(COMPILER.exists() and RUNNER.exists(),'Build Mei for native rendering tests.')
class NativePaletteTests(unittest.TestCase):
    """Builds a palette-backed asset, draws it with the real compiler and emulator, then rewrites
    palette entries at run time and checks the pixels follow."""

    def render(self,tmp,setup):
        Path(tmp,'cart.akr').write_text(f'''cart "Palette test"
import "test.akr"
embed NIGHT: u16 = "night.pal"
embed DAY: u16 = "day.pal"

fn init() {{
    asset_test_load()
{setup}
}}

fn draw() {{
    cls(0)
    dither(false)
    camera(vec3(0.0, 0.0, -5.0), 0.0)
    mesh(ASSET_TEST)
}}
''')
        subprocess.run([str(COMPILER),str(Path(tmp,'cart.akr')),'-o',str(Path(tmp,'cart.mei'))],check=True,capture_output=True)
        subprocess.run([str(RUNNER),str(Path(tmp,'cart.mei')),'--frames','4','--dump',str(Path(tmp,'out.ppm'))],check=True,capture_output=True)
        pixels = Path(tmp,'out.ppm').read_bytes().split(b'\n',3)[3]
        def at(x,y): return tuple(pixels[(y*320+x)*3:(y*320+x)*3+3])
        return at(114,120),at(206,120)

    def test_rewriting_palette_entries_recolours_the_mesh(self):
        from assetkit.compiler import rgb15
        r = palette_recipe()
        with tempfile.TemporaryDirectory() as tmp:
            build(r,tmp)
            Path(tmp,'day.pal').write_bytes(struct.pack('<H',rgb15('#c08040')))
            Path(tmp,'night.pal').write_bytes(struct.pack('<H',rgb15('#20f0f0')))
            def expect(color,tint):
                # The GPU: 5-bit texel expanded to 8 bits, times tint / 128, then the top 5 bits shown.
                out = []
                for k in (1,3,5):
                    c5 = int(color[k:k+2],16)>>3
                    c = min(255,((c5<<3)|(c5>>2))*tint>>7)>>3
                    out.append((c<<3)|(c>>2))
                return tuple(out)
            wall,neon = self.render(tmp,'')
            # A front wall: vertical bake with ambient 0.5 shades it 0.75, a tint of 96.
            self.assertEqual(wall,expect('#c08040',96))
            self.assertEqual(neon,expect('#c08040',128))
            # Rewrite the surface entry only: the surface box changes, the emissive one does not,
            # although both materials have the same default colour.
            wall2,neon2 = self.render(tmp,'    load_palette(ASSET_TEST_SURFACE, NIGHT, 1)')
            self.assertEqual(wall2,expect('#20f0f0',96))
            self.assertEqual(neon2,neon)
            # Drive the emissive entry alone with palette_lerp, as a day/night cycle would.
            wall3,neon3 = self.render(tmp,'    palette_lerp(ASSET_TEST_EMISSIVE, DAY, NIGHT, ASSET_TEST_EMISSIVE_COUNT, 1.0)')
            self.assertEqual(wall3,wall)
            self.assertEqual(neon3,expect('#20f0f0',128))

    def test_kiosk_example_previews_with_palette_materials(self):
        r = json.loads((ROOT/'examples/assets/kiosk.asset.json').read_text())
        r.pop('verification')
        with tempfile.TemporaryDirectory() as tmp:
            report = build(r,tmp,True,COMPILER,RUNNER)
            textured = sum(v['stats']['px_tex'] for v in report['preview']['views'])
            flat = sum(v['stats']['px_flat'] for v in report['preview']['views'])
            self.assertGreater(textured,flat,'Palette-backed faces should cover most of the kiosk.')

    @unittest.skipUnless(PROBE.exists(),'Needs mei-asset-probe.')
    def test_probe_reads_carts_larger_than_two_megabytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            # The mesh is drawn only if the cart's last byte, beyond 2 MB, was read.
            Path(tmp,'pad.bin').write_bytes(bytes(3*1024*1024-1)+b'\7')
            code = source('test',build(recipe(),tmp)['bounds']).replace('fn draw() {','embed PAD: u8 = "pad.bin"\n\nfn draw() {\n    if PAD[len(PAD) - 1] != 7 { return }')
            Path(tmp,'big.akr').write_text(code)
            subprocess.run([str(COMPILER),str(Path(tmp,'big.akr')),'-o',str(Path(tmp,'big.mei')),'--sym',str(Path(tmp,'big.sym'))],check=True,capture_output=True)
            self.assertGreater(Path(tmp,'big.mei').stat().st_size,3*1024*1024)
            symbols = {line.split()[1]:line.split()[0] for line in Path(tmp,'big.sym').read_text().splitlines() if len(line.split()) == 2}
            result = subprocess.run([str(PROBE),str(Path(tmp,'big.mei')),str(Path(tmp,'capture.bin')),
                                     str(int(symbols['G___sv'],16)),'8'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            capture = Path(tmp,'capture.bin').read_bytes()
            self.assertEqual(capture[:4],b'MAV1')
            self.assertGreater(struct.unpack_from('<I',capture,8)[0],0,'The probe did not read the whole cart.')


@unittest.skipUnless(COMPILER.exists() and RUNNER.exists(),'Build Mei for native rendering tests.')
class NativeRenderTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('numpy'),'Optional depth oracle needs NumPy.')
    def test_backpack_matches_independent_depth_oracle(self):
        from mei_asset_oracle import audit
        r = json.loads((ROOT/'examples/assets/robot.asset.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            # Forty steps include yaw 2.334513, where the coarse socket left a
            # one-pixel sorting leak even after removing the hidden torso faces.
            report = audit(r,tmp,'backpack',views=40,compiler=COMPILER,runner=RUNNER)
            self.assertGreater(report['tested_pixels'],500,'No meaningful backpack coverage.')
            self.assertEqual(report['wrong_pixels'],0)

    def test_robot_surface_details_are_visible_across_front_angles(self):
        r = json.loads((ROOT/'examples/assets/robot.asset.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            report = build(r,tmp)
            lo,hi = report['bounds']['min'],report['bounds']['max']
            center = [(a+b)/2 for a,b in zip(lo,hi)]
            scale = 2/max(b-a for a,b in zip(lo,hi))
            radius = math.sqrt(sum(((b-a)*scale/2)**2 for a,b in zip(lo,hi)))
            distance = max(1,radius*2.6)
            for yaw,pitch in ((0,0),(-.65,-.35),(.65,-.35),(-1,0),(1,0),(0,.3),(0,-.6)):
                with self.subTest(yaw=yaw,pitch=pitch):
                    path = Path(tmp)/'face_test.akr'
                    path.write_text(source('robot',report['bounds'],yaw,pitch))
                    subprocess.run([str(COMPILER),str(path),'-o',str(path.with_suffix('.mei'))],check=True,capture_output=True)
                    subprocess.run([str(RUNNER),str(path.with_suffix('.mei')),'--frames','4','--dump',str(path.with_suffix('.ppm'))],check=True,capture_output=True)
                    pixels = path.with_suffix('.ppm').read_bytes().split(b'\n',3)[3]
                    right = (math.cos(yaw),0,-math.sin(yaw))
                    up = (-math.sin(yaw)*math.sin(pitch),math.cos(pitch),-math.cos(yaw)*math.sin(pitch))
                    forward = (math.sin(yaw)*math.cos(pitch),math.sin(pitch),math.cos(yaw)*math.cos(pitch))
                    samples = [((-.21,2.02,-.28),'eye'),((.21,2.02,-.28),'eye'),
                               ((0,1.99,-.28),'dark'),((0,1.23,-.375),'copper')]
                    for x in (-.27,.27):
                        samples.extend([((x,.14,-.39),'boot'),((x,.035,-.4),'sole')])
                    for point,kind in samples:
                        p = tuple((v-c)*scale for v,c in zip(point,center))
                        depth = dot(forward,p)+distance
                        sx = int(160+160*1.299*dot(right,p)/depth)
                        sy = int(120-120*1.732*dot(up,p)/depth)
                        red,green,blue = pixels[(sy*320+sx)*3:(sy*320+sx)*3+3]
                        if kind == 'eye':
                            self.assertGreater(red-blue,60,'An eye was obscured by another face.')
                            self.assertGreater(green-blue,45)
                        elif kind == 'copper':
                            self.assertGreater(red-green,35,'The torso cut across the copper button.')
                            self.assertGreater(green-blue,25)
                        elif kind == 'boot':
                            self.assertGreater(red,120,'The sole or ankle cut across the boot.')
                            self.assertGreater(green,115)
                            self.assertGreater(blue,90)
                        else:
                            self.assertLess(max(red,green,blue),85,f'A shell face cut across the {kind} surface.')

    def test_preview_does_not_overwrite_recipe_with_unusual_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'view_front.akr'
            contents = json.dumps(recipe())
            path.write_text(contents)
            with self.assertRaisesRegex(AssetError,'overwrite'):
                build(recipe(),tmp,True,COMPILER,RUNNER,input_path=str(path))
            self.assertEqual(path.read_text(),contents)

    def test_examples_render_in_real_mei_without_dropped_triangles(self):
        for path in (ROOT/'examples/assets').glob('*.asset.json'):
            if path.name == 'stall.asset.json' and not (PILLOW and NUMPY): continue
            with self.subTest(asset=path.name), tempfile.TemporaryDirectory() as tmp:
                report = build(json.loads(path.read_text()),tmp,True,COMPILER,RUNNER,input_path=str(path),probe=PROBE)
                self.assertEqual((Path(tmp)/'contact.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
                for view in report['preview']['views']:
                    self.assertGreater(view['stats']['tris'],0)
                    self.assertEqual(view['stats']['tris_dropped'],0)
                    self.assertEqual(view['stats']['ticks'],1)
                    raw = (Path(tmp)/('view_'+view['view']+'.ppm')).read_bytes().split(b'\n',3)[3]
                    # Check model area, excluding text bands; visible output cannot be only a HUD.
                    colors = {raw[i:i+3] for y in range(32,208) for x in range(48,272) for i in [(y*320+x)*3]}
                    if 'palette' in report:
                        # Few flat palette colours (one roof entry seen from the top); check coverage.
                        background = raw[:3]
                        drawn = sum(raw[i:i+3] != background for y in range(32,208) for x in range(48,272) for i in [(y*320+x)*3])
                        self.assertGreater(drawn,2000)
                    else:
                        self.assertGreater(len(colors),8)


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Optional depth oracle needs NumPy.')
class VisibilityOracleTests(unittest.TestCase):
    def test_depth_reference_is_independent_of_face_order(self):
        from mei_asset_oracle import reference
        r = recipe(materials={'red':{'color':'#ff0000'},'blue':{'color':'#0000ff'}},lighting={'bake':False})
        r['nodes'] = [
            {'id':'back','op':'box','size':[2,2,.2],'material':'blue','transform':{'translate':[0,0,.2]}},
            {'id':'front','op':'box','size':[1,1,.2],'material':'red','transform':{'translate':[0,0,-.2]}},
        ]
        images=[]
        for nodes in (r['nodes'],list(reversed(r['nodes']))):
            r['nodes']=nodes
            mesh,materials,report=compile_recipe(r)
            binary=native_bytes(mesh,materials,r['lighting'])
            pixels,mask=reference(binary,mesh,report['bounds'],0,0,'red')
            self.assertTrue(mask[120,160])
            self.assertEqual(list(pixels[120,160]),[255,0,0])
            self.assertEqual(list(pixels[120,200]),[0,0,255])
            images.append(pixels)
        self.assertTrue((images[0]==images[1]).all())


def lod_recipe(**lod):
    r = recipe({'id':'body','op':'sphere','radius':1,'rings':6,'segments':12,'material':'paint'},
               materials={'paint':{'color':'#c04020','palette':True},'trim':{'color':'#202020'}})
    r['lod'] = {'levels':[{'distance':12,'nodes':[{'id':'body','op':'sphere','radius':1,'rings':3,'segments':6,'material':'paint'}]},
                          {'distance':30,'nodes':[{'id':'body','op':'box','size':[1.6,1.6,1.6],'material':'trim'}]}],
                'cull':60,**lod}
    return r


class LodTests(unittest.TestCase):
    def test_levels_compile_and_report_triangles(self):
        mesh,materials,report = compile_recipe(lod_recipe())
        rows = report['lod']['levels']
        self.assertEqual([(r['level'],r['distance']) for r in rows],[(0,0),(1,12),(2,30)])
        self.assertEqual([r['triangles'] for r in rows],[len(mesh.faces)]+[len(m.faces) for m,_ in mesh.levels])
        self.assertEqual((report['lod']['cull'],report['lod']['band']),(60,1.0))
        self.assertGreater(rows[0]['triangles'],rows[1]['triangles'])
        # every level draws through level 0's palette entries
        self.assertIs(mesh.levels[0][0].palette,mesh.palette)
        self.assertIsNone(mesh.levels[1][0].palette)
        # a recipe without lod reports as before
        self.assertNotIn('lod',compile_recipe(recipe())[2])

    def test_lod_errors(self):
        r = lod_recipe()
        r['lod']['levels'][1]['distance'] = 12
        with self.assertRaisesRegex(AssetError,'increase') as e: compile_recipe(r)
        self.assertEqual(e.exception.path,'/lod/levels/1/distance')
        with self.assertRaisesRegex(AssetError,'twice the band') as e: compile_recipe(lod_recipe(band=10))
        with self.assertRaises(AssetError) as e: compile_recipe(lod_recipe(cull=25))
        self.assertEqual(e.exception.path,'/lod/cull')
        r = lod_recipe()
        r['lod']['levels'][0]['nodes'][0]['op'] = 'blob'
        with self.assertRaises(AssetError) as e: compile_recipe(r)
        self.assertTrue(e.exception.path.startswith('/lod/levels/0/nodes/0'),e.exception.path)
        r = lod_recipe()
        r['materials']['glow'] = {'color':'#ffff00','class':'emissive'}
        r['lod']['levels'][0]['nodes'][0]['material'] = 'glow'
        with self.assertRaisesRegex(AssetError,'level 0') as e: compile_recipe(r)
        self.assertEqual(e.exception.path,'/lod/levels/0/nodes')
        r = lod_recipe()
        r['lod']['levels'][0]['nodes'][0]['rings'] = 8
        r['lod']['levels'][0]['nodes'][0]['segments'] = 16
        self.assertIn('lod_not_simpler',[w['code'] for w in compile_recipe(r)[2]['warnings']])

    def test_build_writes_each_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build(lod_recipe(),tmp)
            for k in (1,2):
                self.assertTrue(Path(tmp,f'test.lod{k}.bin').is_file())
            akr = Path(tmp,'test.akr').read_text()
            self.assertIn('embed ASSET_TEST_LOD2: Mesh = "test.lod2.bin"',akr)
            self.assertEqual(report['lod']['levels'][2]['triangles'],12)
            self.assertEqual(struct.unpack_from('<H',Path(tmp,'test.lod2.bin').read_bytes(),2)[0],12)

    @unittest.skipUnless(PROBE.exists() and COMPILER.exists() and importlib.util.find_spec('numpy'),
                         'The Asset Checker needs NumPy, meic and mei-asset-probe.')
    def test_asset_checker_judges_every_level(self):
        from assetkit.visibility import verify
        with tempfile.TemporaryDirectory() as tmp:
            r = verify(lod_recipe(),{'yaw_steps':4,'pitches':[0],'distances':[1.5]},tmp,COMPILER,PROBE)
            self.assertTrue(r['ok'])
            self.assertEqual([(l['level'],l['ok']) for l in r['lod']],[(1,True),(2,True)])
            self.assertEqual(r['lod'][1]['faces'],12)
            self.assertTrue(Path(tmp,'lod2','verification.json').is_file())
            # a level that fails fails the asset
            bad = lod_recipe()
            bad['lod']['levels'][1]['nodes'].append({'id':'twin','op':'box','size':[1.6,1.6,1.6],'material':'trim'})
            r = verify(bad,{'yaw_steps':4,'pitches':[0],'distances':[1.5]},None,COMPILER,PROBE)
            self.assertFalse(r['ok'])
            self.assertEqual([l['ok'] for l in r['lod']],[True,False])


class PolicyTests(unittest.TestCase):
    def test_world_scale_draws_the_mesh_at_its_own_size(self):
        bounds = {'min':[-15,0,-1],'max':[15,10,1]}
        self.assertIn('mat4_scale(vec3(1.0000000, 1.0000000, 1.0000000))',source('big',bounds,world=True))
        self.assertIn('mat4_scale(vec3(0.0666667,',source('big',bounds))
        for policy,path in (({'scale':'huge'},'/verification/scale'),({'yaw_range_degrees':[10]},'/verification/yaw_range_degrees')):
            with self.assertRaises(AssetError) as e: compile_recipe(recipe(verification=policy))
            self.assertEqual(e.exception.path,path)

    @unittest.skipUnless(PROBE.exists() and COMPILER.exists() and importlib.util.find_spec('numpy'),
                         'The Asset Checker needs NumPy, meic and mei-asset-probe.')
    def test_yaw_range_and_world_scale(self):
        from assetkit.visibility import verify
        wall = recipe({'id':'panel','op':'box','size':[20,6,0.4],'open':['back'],'transform':{'translate':[0,3,0]}})
        r = verify(wall,{'yaw_steps':5,'pitches':[0],'distances':[1],'yaw_range_degrees':[-60,60],'scale':'world'},
                   None,COMPILER,PROBE)
        self.assertTrue(r['ok'])
        yaws = sorted({round(math.degrees(v['camera']['yaw']),6) for v in r['views']})
        self.assertEqual(yaws,[-60,-30,0,30,60])
        self.assertEqual(r['profile']['scale'],'world')

    @unittest.skipUnless(PROBE.exists() and COMPILER.exists() and importlib.util.find_spec('numpy'),
                         'The Asset Checker needs NumPy, meic and mei-asset-probe.')
    def test_edge_margin(self):
        from assetkit.visibility import verify
        # thin slats in front of a rail: they truly mis-sort, near their edges and inside them
        nodes = [{'id':'rail','op':'box','size':[4,0.15,0.1],'transform':{'translate':[0,0.8,0]}}]
        for i in range(5):
            nodes.append({'id':f's{i}','op':'box','size':[0.04,1.0,0.25],'transform':{'translate':[-1.8+0.9*i,0.5,0.2]}})
        fence = recipe(); fence['nodes'] = nodes
        cams = {'yaw_steps':8,'pitches':[-0.35,0],'distances':[1]}
        exact = verify(fence,{**cams,'edge_margin':0},None,COMPILER,PROBE)['totals']
        loose = verify(fence,cams,None,COMPILER,PROBE)
        self.assertEqual(loose['profile']['edge_margin'],1.0,'the default is the World Checker\'s')
        t = loose['totals']
        self.assertEqual(exact['undecided_pixels'],0)
        self.assertGreater(exact['wrong_pixels'],t['wrong_pixels'])
        # the margin hides wrong pixels near outlines, and says how many
        self.assertGreater(t['undecided_wrong_pixels'],0)
        self.assertEqual(t['wrong_pixels']+t['undecided_wrong_pixels'],exact['wrong_pixels'])
        self.assertEqual(t['tested_pixels']+t['undecided_pixels'],exact['tested_pixels'])
        self.assertEqual(t['coverage_errors'],exact['coverage_errors'])
        # a pole no wider than the margin: nothing decided, coverage judged, a pass
        pole = verify(recipe({'op':'box','size':[0.03,3,0.03]}),{**cams,'distances':[1.5]},None,COMPILER,PROBE)
        self.assertTrue(pole['ok'])
        self.assertEqual(pole['totals']['tested_pixels'],0)
        self.assertGreater(pole['totals']['undecided_pixels'],0)


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Visibility verification needs NumPy.')
class GeometryAuditTests(unittest.TestCase):
    def test_adjacent_triangles_are_not_intersections(self):
        from assetkit.geometry_audit import geometry_audit
        mesh,_,_=compile_recipe(recipe())
        self.assertTrue(geometry_audit(mesh)['ok'])

    def test_identical_surfaces_across_named_parts_are_detected(self):
        from assetkit.geometry_audit import geometry_audit
        r=recipe();r['nodes'].append({'id':'duplicate','op':'box','size':[2,2,2]})
        mesh,_,_=compile_recipe(r)
        report=geometry_audit(mesh)
        self.assertFalse(report['ok'])
        self.assertEqual(report['counts']['duplicate_face'],12)
        self.assertEqual(report['findings'][0]['a']['part'],'body')
        self.assertEqual(report['findings'][0]['b']['part'],'duplicate')

    def test_crossing_and_coplanar_overlaps(self):
        from assetkit.geometry_audit import geometry_audit
        r=recipe({'op':'mesh','vertices':[[-1,-1,-.2],[1,-1,.2],[0,1,0],[-1,-1,.2],[1,-1,-.2]],
                  'faces':[[0,1,2],[3,4,2]]})
        mesh,_,_=compile_recipe(r)
        self.assertEqual(geometry_audit(mesh)['counts']['surface_intersection'],1)
        r=recipe({'op':'mesh','vertices':[[0,0,0],[2,0,0],[0,2,0],[.2,.2,0],[1,.2,0],[.2,1,0]],
                  'faces':[[0,1,2],[3,4,5]]})
        mesh,_,_=compile_recipe(r)
        self.assertEqual(geometry_audit(mesh)['counts']['coplanar_overlap'],1)

    def test_cycle_witness_excludes_downstream_nodes(self):
        from assetkit.visibility import cycle_witness
        self.assertEqual(cycle_witness({0:{1},1:{2},2:{0,3},3:{4}}),[0,1,2,0])
        self.assertEqual(cycle_witness({0:{1},1:{2},2:{3}}),[])


@unittest.skipUnless(importlib.util.find_spec('numpy') and COMPILER.exists() and PROBE.exists(),
                     'Native visibility gate needs NumPy, meic and mei-asset-probe.')
class NativeVisibilityGateTests(unittest.TestCase):
    profile={'yaw_steps':4,'pitches':[0],'distances':[1]}

    def checked(self,r,profile_extra=None,**kw):
        from assetkit.visibility import verify
        return verify(r,{**self.profile,**(profile_extra or {})},compiler=COMPILER,probe=PROBE,**kw)

    def overlap(self):
        r=recipe()
        r['nodes']=[{'id':'body','op':'box','size':[2,2,.6]},
                    {'id':'plate','op':'box','size':[1,1,.08],'transform':{'translate':[0,0,-.36]}}]
        return r

    def test_closed_convex_mesh_matches_native_coverage_including_edges(self):
        report=self.checked(recipe())
        self.assertTrue(report['ok'])
        self.assertGreater(report['totals']['tested_pixels'],10000)
        self.assertEqual(report['totals']['wrong_pixels'],0)
        self.assertEqual(report['totals']['coverage_errors'],0)
        self.assertEqual(report['totals']['cyclic_views'],0)

    def test_identically_colored_surfaces_cannot_hide_ordering_errors(self):
        report=self.checked(self.overlap())
        self.assertTrue(report['geometry']['ok'])
        self.assertFalse(report['ok'])
        self.assertGreater(report['totals']['wrong_pixels'],100)
        issue=next(v['issues'][0] for v in report['views'] if v['issues'])
        self.assertEqual(issue['drawn']['material'],issue['expected']['material'])
        self.assertEqual({issue['drawn']['part'],issue['expected']['part']},{'body','plate'})
        self.assertIn('sample_pixel',issue)

    def test_smooth_mesh_uses_same_native_identity_coverage(self):
        r=recipe({'op':'sphere','radius':1,'rings':4,'segments':8},
                 materials={'default':{'color':'#cf8753','smooth':True}})
        report=self.checked(r)
        self.assertTrue(report['ok'])
        self.assertEqual(report['totals']['coverage_errors'],0)

    def test_double_sided_surfaces_use_native_culling_rules(self):
        r=recipe({'op':'mesh','vertices':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],'faces':[[0,1,2,3]]},
                 materials={'default':{'color':'#ffffff','double_sided':True}})
        report=self.checked(r)
        self.assertTrue(report['ok'])
        self.assertTrue(all(v['tested_pixels']>0 for v in report['views']))

    def test_palette_backed_faces_use_the_same_gate(self):
        report=self.checked(palette_recipe())
        self.assertTrue(report['ok'])
        self.assertEqual(report['totals']['coverage_errors'],0)
        r=self.overlap();r['materials']={'default':{'color':'#808080','palette':True}}
        report=self.checked(r)
        self.assertFalse(report['ok'],'Palette-backed faces must not hide ordering errors.')
        self.assertGreater(report['totals']['wrong_pixels'],100)

    def test_crossing_depths_have_cycle_and_split_diagnostic(self):
        r=recipe({'op':'mesh','vertices':[[-1,-1,-.2],[1,-1,.2],[0,1,0],[-1,-1,.2],[1,-1,-.2]],
                  'faces':[[0,1,2],[3,4,2]]},materials={'default':{'color':'#ffffff','double_sided':True}})
        report=self.checked(r)
        self.assertFalse(report['ok'])
        self.assertGreater(report['totals']['cyclic_views'],0)
        self.assertTrue(any(v['ordering_graph']['crossing_pairs'] for v in report['views']))

    def test_required_policy_blocks_export_and_preserves_previous_artifacts(self):
        from mei_assets import VerificationFailure
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            originals={name:(Path(tmp)/name).read_bytes() for name in ('test.bin','test.akr','report.json')}
            r=self.overlap();r['verification']={'required':True,**self.profile}
            with self.assertRaises(VerificationFailure):build(r,tmp,compiler=COMPILER,probe=PROBE)
            for name,data in originals.items():self.assertEqual((Path(tmp)/name).read_bytes(),data)
            failure=json.loads((Path(tmp)/'verification.failed.json').read_text())
            self.assertFalse(failure['ok'])
            self.assertTrue(failure['images'])
            self.assertTrue(all((Path(tmp)/p).is_file() for p in failure['images']))

    def test_successful_checked_export_keeps_real_colors(self):
        r=recipe(materials={'default':{'color':'#f02040'}},lighting={'bake':False},
                 verification={'required':True,**self.profile})
        mesh,mats,_=compile_recipe(r)
        with tempfile.TemporaryDirectory() as tmp:
            report=build(r,tmp,compiler=COMPILER,probe=PROBE)
            self.assertTrue(report['verification']['ok'])
            self.assertEqual((Path(tmp)/'test.bin').read_bytes(),native_bytes(mesh,mats,r['lighting']))
            self.assertTrue((Path(tmp)/'verification.json').exists())

    def test_verify_cli_returns_failure_json_and_reports_profile(self):
        result=subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'verify','-',
                               '--yaw-steps','4','--pitches=0','--distances=1',
                               '--compiler',str(COMPILER),'--probe',str(PROBE)],
                              input=json.dumps(self.overlap()),text=True,capture_output=True)
        self.assertEqual(result.returncode,1)
        self.assertNotIn('Traceback',result.stderr)
        report=json.loads(result.stdout)
        self.assertFalse(report['ok'])
        self.assertEqual(report['totals']['views'],4)
        self.assertEqual(report['profile']['far'],100)

    def test_invalid_profile_cannot_silently_reduce_coverage(self):
        from assetkit.visibility import verify
        for overrides in ({'yaw_steps':0},{'pitches':[]},{'distances':[float('nan')]},{'geometry':'ignore'},
                          {'depth':1},{'perspective':'yes'}):
            with self.assertRaises(AssetError):verify(recipe(),overrides,compiler=COMPILER,probe=PROBE)

    def test_depth_policy_judges_the_asset_as_the_depth_buffer_draws_it(self):
        # docs/ASSETKIT.md, "Depth mode": the depth test orders faces per pixel, so a plate on a
        # body and two crossing faces pass; ordering is a regression check (0 wrong pixels).
        depth={'depth':True,'perspective':True}
        plain=self.checked(self.overlap())
        self.assertNotIn('depth_mode',plain,'a report without depth is as before')
        report=self.checked(dict(self.overlap(),verification={'required':True,**depth}))
        self.assertTrue(report['ok'])
        self.assertEqual((report['totals']['wrong_pixels'],report['totals']['coverage_errors']),(0,0))
        self.assertEqual(report['profile']['depth'],True)
        self.assertEqual(report['depth_mode']['key_steps'],2)
        self.assertGreater(report['totals']['tested_pixels'],plain['totals']['tested_pixels']/2)
        crossing=recipe({'op':'mesh','vertices':[[-1,-1,-.2],[1,-1,.2],[0,1,0],[-1,-1,.2],[1,-1,-.2]],
                         'faces':[[0,1,2],[3,4,2]]},materials={'default':{'color':'#ffffff','double_sided':True}})
        self.assertFalse(self.checked(crossing)['ok'])
        report=self.checked(crossing,profile_extra=depth)
        self.assertTrue(report['ok'],report['totals'])
        self.assertEqual(report['geometry']['counts'],{'surface_intersection':1},'still reported')
        self.assertEqual(report['totals']['cyclic_views'],0)
        # what the depth buffer does not fix still fails: coplanar overlaps (z-fighting)
        coplanar=recipe({'op':'mesh','vertices':[[0,0,0],[2,0,0],[0,2,0],[.2,.2,0],[1,.2,0],[.2,1,0]],
                         'faces':[[0,1,2],[3,4,5]]})
        self.assertFalse(self.checked(coplanar,profile_extra=depth)['ok'])


# ---------------------------------------------------------------------------------------------
# Textures (docs/ASSETKIT.md, "Textures")

DEPTH_POLICY = {'required':False,'depth':True,'perspective':True}


def textured(texture, node=None, **extra):
    """A recipe whose default material has a texture."""
    return recipe(node,**{'materials':{'default':{'color':'#808080','texture':texture}},
                          'lighting':{'bake':False},**extra})


def quad(width=2.0, height=1.0, z=0.0, **extra):
    """A quad facing -Z (the front camera)."""
    return {'id':'panel','op':'mesh','vertices':[[-width/2,-height/2,z],[width/2,-height/2,z],
                                                 [width/2,height/2,z],[-width/2,height/2,z]],
            'faces':[[3,2,1,0]],**extra}


def corners(mesh):
    """face -> {(rounded position): texture coordinate}."""
    out = []
    for f in mesh.faces:
        out.append({tuple(round(c,4) for c in mesh.vertices[i]):uv for i,uv in zip(f.indices,f.texcoords)})
    return out


def write_png(path, rows):
    from PIL import Image
    image = Image.new('RGBA',(len(rows[0]),len(rows)))
    image.putdata([p for row in rows for p in row])
    image.save(path)


class TextureSourceTests(unittest.TestCase):
    def test_patterns_are_deterministic_and_check_their_divisions(self):
        from assetkit.textures import PATTERNS
        for name in PATTERNS:
            with self.subTest(pattern=name):
                r = textured({'pattern':name,'colors':['#a0522d','#d8d0c0','#704020','#302010']})
                a,_,_ = compile_recipe(r); b,_,_ = compile_recipe(copy.deepcopy(r))
                self.assertEqual(a.textures['textures']['default'].tile.frames,b.textures['textures']['default'].tile.frames)
                self.assertEqual((a.textures['textures']['default'].width,a.textures['textures']['default'].height),(16,16))
        with self.assertRaisesRegex(AssetError,'divide') as error:
            compile_recipe(textured({'pattern':'brick','colors':['#a0522d','#d8d0c0'],'params':{'courses':3}}))
        self.assertEqual(error.exception.path,'/materials/default/texture/params/courses')
        with self.assertRaises(AssetError) as error:
            compile_recipe(textured({'pattern':'brick','colors':['#a0522d','#d8d0c0'],'params':{'rows':4}}))
        self.assertEqual(error.exception.path,'/materials/default/texture/params/rows')

    def test_texel_grid_colours_and_clear(self):
        grid = {'texels':['0110','1221','1221','0110'],'colors':['#000000','#ff0000','#00ff00'],'projection':'fit'}
        mesh,_,_ = compile_recipe(textured(grid))
        tex = mesh.textures['textures']['default']
        self.assertEqual((tex.width,tex.height,tex.cutout,tex.quantised),(4,4,False,False))
        self.assertEqual(tex.tile.frames[0][1],[0x1f,0x3e0,0x3e0,0x1f])     # rgb15 red, green
        # a clear colour is a hole; holes need the depth buffer
        holed = dict(grid,clear='#000000')
        with self.assertRaisesRegex(AssetError,'depth buffer') as error:
            compile_recipe(textured(holed))
        self.assertEqual(error.exception.path,'/materials/default/texture')
        mesh,_,_ = compile_recipe(textured(holed,verification=DEPTH_POLICY))
        tex = mesh.textures['textures']['default']
        self.assertTrue(tex.cutout)
        self.assertEqual(tex.tile.frames[0][0],[None,0x1f,0x1f,None])
        for bad,path in (({**grid,'texels':['01','012']},'/texels'),({**grid,'texels':['0123']},'/texels'),
                         ({**grid,'clear':'#123456'},'/clear'),({**grid,'params':{}},'/params'),
                         ({**grid,'image':'x.png'},''),({**grid,'axis':'x'},'/axis'),({**grid,'scale':[1,1]},'/scale')):
            with self.subTest(bad=bad), self.assertRaises(AssetError) as error:
                compile_recipe(textured(bad))
            self.assertEqual(error.exception.path,'/materials/default/texture'+path)

    def test_quantisation_is_exact_when_colours_fit_and_reserves_index_zero(self):
        from assetkit.textures import quantise
        few = [[[(x*16,0,0) for x in range(15)]]]
        out,before,quantised = quantise(few,15)
        self.assertEqual((before,quantised),(15,False))
        self.assertEqual(out[0][0],[(x*16)>>3 for x in range(15)])
        many = [[[(x*8,y*8,0) for x in range(8)] for y in range(8)]]
        out,before,quantised = quantise(many,15)
        self.assertEqual((before,quantised),(64,True))
        self.assertLessEqual(len({c for row in out[0] for c in row}),15)
        self.assertEqual(out,quantise(copy.deepcopy(many),15)[0])          # deterministic
        # placed: indices 1-15, never 0
        texels = ['0123456789abcdef']*16
        r = textured({'texels':texels,'colors':[f'#{k*16:02x}{255-k*16:02x}40' for k in range(16)],'projection':'fit'})
        mesh,_,report = compile_recipe(r)
        place = mesh.textures['packing'].placements[mesh.textures['textures']['default'].tile.key]
        self.assertEqual(report['textures']['list'][0]['quantised_from'],16)
        self.assertEqual(sorted(set(place.index.values())),list(range(1,16)))

    def test_eight_bit_textures_keep_255_colours_and_cost_twice(self):
        colours = [f'#{k*16:02x}{k*16:02x}{k*16:02x}' for k in range(16)]
        rows = ['0123456789abcdef']*8
        four,_,rep4 = compile_recipe(textured({'texels':rows,'colors':colours,'projection':'fit'}))
        eight,_,rep8 = compile_recipe(textured({'texels':rows,'colors':colours,'projection':'fit','bits':8}))
        self.assertEqual(rep4['textures']['list'][0]['colours'],15)
        self.assertEqual(rep8['textures']['list'][0]['colours'],16)
        self.assertEqual(rep8['textures']['list'][0]['vram_bytes'],17*9)     # with the gutter
        self.assertEqual(rep4['textures']['list'][0]['vram_bytes'],9*9)      # 4-bit rows of whole bytes
        packing = eight.textures['packing']
        self.assertEqual(packing.slot_bits,{14:8})
        self.assertEqual(sorted(packing.palettes),[(8,14)])
        flags,_,tex,palette,*_ = faces_of(native_bytes(eight,{'default':{'color':'#808080','texture':{}}},{'bake':False}))[0]
        self.assertEqual((flags&2,tex&16,tex&15,palette),(2,0,14,14))
        manifest = material_manifest(eight,{'default':{'color':'#808080'}},textured({}))
        self.assertEqual(manifest['textures']['list'][0]['night'],'multiply')
        self.assertEqual(manifest['textures']['list'][0]['first_colour'],14*256)

    @unittest.skipUnless(PILLOW,'Image import needs Pillow.')
    def test_images_sheets_and_animations(self):
        with tempfile.TemporaryDirectory() as tmp:
            red,blue,clear = (255,0,0,255),(0,0,255,255),(0,0,0,0)
            write_png(Path(tmp,'icon.png'),[[red,clear],[blue,red]])
            mesh,_,_ = compile_recipe(textured({'image':'icon.png','projection':'fit'},verification=DEPTH_POLICY),tmp)
            tex = mesh.textures['textures']['default']
            self.assertEqual(tex.tile.frames[0],[[0x1f,None],[0x7c00,0x1f]])
            self.assertTrue(tex.cutout)
            self.assertEqual(tex.source['sha256'],__import__('hashlib').sha256(Path(tmp,'icon.png').read_bytes()).hexdigest())
            # a uniform grid: cells by [column, row]
            write_png(Path(tmp,'grid.png'),[[red]*2+[blue]*2]*2)
            sheets = {'s':{'image':'grid.png','grid':[2,2]}}
            mesh,_,_ = compile_recipe(textured({'sheet':'s','cell':[1,0],'projection':'fit'},sheets=sheets),tmp)
            self.assertEqual(mesh.textures['textures']['default'].tile.frames[0],[[0x7c00]*2]*2)
            with self.assertRaisesRegex(AssetError,'columns'):
                compile_recipe(textured({'sheet':'s','cell':[2,0],'projection':'fit'},sheets=sheets),tmp)
            # named rectangles in grid.sheet.json beside the image; an animation of two frames
            Path(tmp,'grid.sheet.json').write_text(json.dumps({'format':'mei-sheet','version':1,
                                                                'cells':{'a':[0,0,2,2],'b':[2,0,2,2]}}))
            named = {'s':{'image':'grid.png'}}
            anim = {'sheet':'s','frames':['a','b'],'ticks':8,'projection':'fit'}
            mesh,mats,report = compile_recipe(textured(anim,sheets=named),tmp)
            self.assertEqual(len(mesh.textures['textures']['default'].tile.frames),2)
            self.assertEqual(report['textures']['list'][0]['frames'],2)
            manifest = material_manifest(mesh,mats,textured(anim,sheets=named))
            animation = manifest['textures']['animations'][0]
            self.assertEqual({k:animation[k] for k in ('frames','ticks','rows','row_bytes','stride')},
                             {'frames':2,'ticks':8,'rows':3,'row_bytes':2,'stride':128})
            place = mesh.textures['packing'].placements[animation['tile']]
            self.assertEqual(animation['vram'],place.slot*32768+place.y*128+place.x//2)
            with self.assertRaisesRegex(AssetError,'ticks'):
                compile_recipe(textured({'sheet':'s','frames':['a','b'],'projection':'fit'},sheets=named),tmp)
            with self.assertRaisesRegex(AssetError,'no cell'):
                compile_recipe(textured({'sheet':'s','cell':'c','projection':'fit'},sheets=named),tmp)
            # frames whose holes differ are refused
            write_png(Path(tmp,'grid.png'),[[red,clear,blue,blue],[red]*2+[blue]*2])
            with self.assertRaisesRegex(AssetError,'holes'):
                compile_recipe(textured(anim,sheets=named,verification=DEPTH_POLICY),tmp)
            Path(tmp,'notpng.png').write_text('hello')
            with self.assertRaises(AssetError):
                compile_recipe(textured({'image':'notpng.png','projection':'fit'}),tmp)

    def test_missing_pillow_is_a_clear_error(self):
        saved = sys.modules.get('PIL')
        sys.modules['PIL'] = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp,'x.png').write_bytes(b'')
                with self.assertRaisesRegex(AssetError,'Pillow'):
                    compile_recipe(textured({'image':'x.png','projection':'fit'}),tmp)
        finally:
            if saved is None: del sys.modules['PIL']
            else: sys.modules['PIL'] = saved


class TextureProjectionTests(unittest.TestCase):
    def test_box_projection_reads_from_outside_on_every_side(self):
        r = textured({'pattern':'checker','colors':['#000000','#ffffff'],'projection':'box','offset':[.5,.5]},
                     {'id':'cube','op':'box','size':[1,1,1]})
        mesh,_,_ = compile_recipe(r)
        # front face (-Z): left edge u 0, right edge u 16, top v 0
        front = {}
        for f in corners(mesh):
            if all(p[2] == -.5 for p in f): front.update(f)
        self.assertEqual(front[(-.5,.5,-.5)],(0,0))
        self.assertEqual(front[(.5,-.5,-.5)],(16,16))
        right = {}
        for f in corners(mesh):
            if all(p[0] == .5 for p in f): right.update(f)
        self.assertEqual(right[(.5,.5,-.5)],(0,0))           # seen from +X, -Z is on the left
        top = {}
        for f in corners(mesh):
            if all(p[1] == .5 for p in f): top.update(f)
        self.assertEqual(top[(-.5,.5,.5)],(0,0))             # from above, +Z is up

    def test_planar_scale_offset_and_flip(self):
        base = {'pattern':'checker','colors':['#000000','#ffffff'],'projection':'planar','axis':'z','scale':[2,1]}
        def uv(texture):
            mesh,_,_ = compile_recipe(textured(texture,quad(2,1)))
            return {k:v for f in corners(mesh) for k,v in f.items()}
        plain = uv(base)
        left,right,top = plain[(-1,-.5,0)],plain[(1,-.5,0)],plain[(-1,.5,0)]
        self.assertEqual(right[0]-left[0],16)                # 2 units at 2 a repeat: one repeat
        self.assertEqual(top[1]-left[1],-16)                 # v runs down; 1 unit at 1 a repeat
        self.assertEqual(left[0]%16,8)                       # anchored at the primitive's origin (x -1: half a repeat)
        shifted = uv({**base,'offset':[.25,0]})
        self.assertEqual((shifted[(-1,-.5,0)][0]-left[0])%16,4)
        flipped = uv({**base,'flip':'u'})
        self.assertEqual(flipped[(1,-.5,0)][0]-flipped[(-1,-.5,0)][0],-16)

    def test_fit_covers_each_face_exactly(self):
        sign = {'texels':['01']*4,'colors':['#000000','#ffffff'],'projection':'fit'}
        mesh,_,_ = compile_recipe(textured(sign,quad(3,1)))
        uv = {k:v for f in corners(mesh) for k,v in f.items()}
        self.assertEqual(uv,{(-1.5,-.5,0):(0,4),(1.5,-.5,0):(2,4),(1.5,.5,0):(2,0),(-1.5,.5,0):(0,0)})
        mesh,_,_ = compile_recipe(textured({**sign,'rotate':90},quad(3,1)))
        uv = {k:v for f in corners(mesh) for k,v in f.items()}
        self.assertEqual(uv[(-1.5,.5,0)],(0,4))              # turned clockwise: the texture's bottom-left is top left
        mesh,_,_ = compile_recipe(textured({**sign,'flip':'u'},quad(3,1)))
        uv = {k:v for f in corners(mesh) for k,v in f.items()}
        self.assertEqual(uv[(-1.5,.5,0)],(2,0))
        with self.assertRaisesRegex(AssetError,'drawn once'):
            compile_recipe(textured({**sign,'offset':[.5,0]},quad(3,1)))

    def test_cylindrical_rounds_repeats_around_and_disc_centres(self):
        r = textured({'pattern':'stripes','colors':['#000000','#ffffff'],'projection':'cylindrical','scale':[1,1]},
                     {'id':'drum','op':'cylinder','radius':1,'height':1,'segments':12,'caps':False})
        mesh,_,_ = compile_recipe(r)
        # around = round(2 pi / 1) = 6 repeats: each of 12 segments spans half a repeat, 8 texels
        for f in mesh.faces:
            us = [u for u,_ in f.texcoords]
            self.assertEqual(max(us)-min(us),8)
        r = textured({'texels':['01']*2,'colors':['#000000','#ffffff'],'projection':'disc','axis':'y'},
                     {'id':'cap','op':'cylinder','radius':1,'height':.1,'segments':8})
        mesh,_,_ = compile_recipe(r)
        top = [f for f in corners(mesh) if all(p[1] == .05 for p in f)]
        uv = {k:v for f in top for k,v in f.items()}
        self.assertEqual(uv[(1.0,.05,0.0)],(2,1))            # +X: the right edge, centre row
        self.assertEqual(uv[(-1.0,.05,0.0)],(0,1))

    def test_hand_uvs_in_mesh_nodes(self):
        node = quad(2,1,uvs=[[0,1],[2,1],[2,0],[0,0]])
        mesh,_,_ = compile_recipe(textured({'pattern':'checker','colors':['#000000','#ffffff'],'projection':'planar'},node))
        uv = {k:v for f in corners(mesh) for k,v in f.items()}
        self.assertEqual(uv[(1,-.5,0)],(32,16))
        with self.assertRaisesRegex(AssetError,'one'):
            compile_recipe(textured({'pattern':'checker','colors':['#000000','#ffffff']},quad(uvs=[[0,0]]*3)))

    def test_long_faces_are_split_without_t_junctions(self):
        # a 20 x 1 strip at 16 texels a unit spans 320 texels: more than the GPU's 255
        node = {'id':'strip','op':'box','size':[20,1,1]}
        mesh,_,report = compile_recipe(textured({'pattern':'brick','colors':['#a0522d','#d8d0c0'],
                                                 'projection':'box','scale':[1,1]},node))
        self.assertGreater(report['textures']['split_faces'],0)
        self.assertEqual(report['triangles'],12+report['textures']['split_faces'])
        for f in mesh.faces:
            self.assertLessEqual(max(max(u,v) for u,v in f.texcoords),255)
            self.assertGreaterEqual(min(min(u,v) for u,v in f.texcoords),0)
        # no vertex lies inside another face's edge
        for f in mesh.faces:
            for k in range(3):
                a,b = (mesh.vertices[f.indices[j]] for j in (k,(k+1)%3))
                for i,p in enumerate(mesh.vertices):
                    if i in f.indices: continue
                    ab,ap = sub(b,a),sub(p,a)
                    if dot(cross(ab,ap),cross(ab,ap)) < 1e-12 and 0 < dot(ap,ab) < dot(ab,ab):
                        self.fail(f'T-junction: vertex {i} on an edge of face {f.indices}')
        # the volume is unchanged
        self.assertAlmostEqual(volume(mesh),20.0,places=6)
        # a short box is not split
        _,_,report = compile_recipe(textured({'pattern':'brick','colors':['#a0522d','#d8d0c0']},{'id':'b','op':'box','size':[2,1,1]}))
        self.assertEqual(report['textures']['split_faces'],0)

    def test_at_most_seven_repeating_textures(self):
        materials = {f'm{k}':{'color':'#808080','texture':{'pattern':'checker','colors':['#000000',f'#0000{k*16:02x}']}}
                     for k in range(8)}
        nodes = [{'id':f'b{k}','op':'box','size':[1,1,1],'material':f'm{k}','transform':{'translate':[2*k,0,0]}} for k in range(8)]
        with self.assertRaisesRegex(AssetError,'7 texture') as error:
            compile_recipe(recipe(**{'materials':materials}) | {'nodes':nodes})
        self.assertEqual(error.exception.path,'/materials')
        mesh,_,report = compile_recipe(recipe(**{'materials':dict(list(materials.items())[:7])}) | {'nodes':nodes[:7]})
        self.assertEqual(report['textures']['windows'],7)

    def test_native_faces_windows_and_tints(self):
        r = recipe(**{'materials':{'wall':{'color':'#808080','texture':{'pattern':'brick','colors':['#a0522d','#d8d0c0']}},
                                   'sign':{'color':'#808080','class':'emissive','texture':{'texels':['01'],'colors':['#000000','#ffffff'],'projection':'fit'}}},
                      'lighting':{'mode':'vertical','ambient':.5}}) | {'nodes':[
            {'id':'wall','op':'box','size':[1,1,1],'material':'wall'},
            {'id':'sign','op':'mesh','material':'sign','vertices':[[-1,1,-1],[1,1,-1],[1,2,-1],[-1,2,-1]],'faces':[[0,1,2,3]]}]}
        mesh,mats,_ = compile_recipe(r)
        binary = native_bytes(mesh,mats,r['lighting'])
        packing = mesh.textures['packing']
        wall = packing.placements[mesh.textures['textures']['wall'].tile.key]
        sign = packing.placements[mesh.textures['textures']['sign'].tile.key]
        _,_,_,_,table = struct.unpack_from('<HHIII',binary)
        self.assertEqual(struct.unpack_from('<H',binary,table)[0],wall.halfword())
        for face,(flags,_,tex,palette,*rest) in zip(mesh.faces,faces_of(binary)):
            colours,uvs = rest[4:8],rest[8:12]
            self.assertEqual(flags&2,2)
            place = wall if face.material == 'wall' else sign
            self.assertEqual((tex&15,bool(tex&16),palette),(place.slot,True,place.palette))
            if face.material == 'wall':
                self.assertEqual(tex>>5,1)
                self.assertTrue(all((uv&255) <= 255 for uv in uvs))
            else:
                self.assertEqual(tex>>5,0)
                self.assertEqual(colours[0],0x808080)               # emissive: unshaded tint
                self.assertTrue(all(sign.x <= (uv&255) <= sign.x+2 and sign.y <= uv>>8 <= sign.y+1 for uv in uvs[:3]))
        sides = [rest[4] for f,(_,_,_,_,*rest) in zip(mesh.faces,faces_of(binary))
                 if f.material == 'wall' and all(abs(mesh.vertices[i][0]-.5) < 1e-9 for i in f.indices)]
        self.assertEqual(sides,[0x606060]*2)                        # a wall shades 0.75: tint 96

    def test_levels_of_detail_share_level_zero_textures(self):
        brick = {'pattern':'brick','colors':['#a0522d','#d8d0c0']}
        r = recipe(**{'materials':{'brick':{'color':'#a0522d','texture':brick},
                                   'other':{'color':'#808080','texture':{**brick,'colors':['#000000','#ffffff']}}}}) | {
            'nodes':[{'id':'b','op':'box','size':[1,1,1],'material':'brick'}],
            'lod':{'levels':[{'distance':10,'nodes':[{'id':'b','op':'box','size':[1,1,1],'material':'brick','open':['bottom']}]}]}}
        mesh,_,_ = compile_recipe(r)
        self.assertIs(mesh.levels[0][0].textures['packing'],mesh.textures['packing'])
        r['lod']['levels'][0]['nodes'][0]['material'] = 'other'
        with self.assertRaisesRegex(AssetError,'level 0') as error:
            compile_recipe(r)
        self.assertEqual(error.exception.path,'/lod/levels/0/nodes')


class TexturePackingTests(unittest.TestCase):
    def tile(self, w, h, colour=1, bits=4, window=False):
        from kitcore.texpack import Tile
        return Tile(w,h,bits,[[[colour]*w for _ in range(h)]],window=window,name=f'{w}x{h}')

    def test_duplicates_window_origins_palettes_and_reserved_space(self):
        from kitcore.texpack import pack
        tiles = [self.tile(16,16,1,window=True),self.tile(16,16,1,window=True),self.tile(32,8,2),self.tile(5,7,3)]
        packing = pack(tiles,slots=[14],reserved=[(14,0,0,16,8)])
        self.assertEqual(len(packing.placements),3)                  # the two equal tiles are one
        for key,place in packing.placements.items():
            self.assertEqual((place.x%8,place.y%8),(0,0))
            self.assertFalse(place.x < 16 and place.y < 8,'the reserved swatch block is free')
        self.assertEqual(sorted(packing.palettes),[(4,0)])            # three colours share one palette
        self.assertEqual(packing.palettes[4,0],[1,2,3])
        first,data = packing.slot_image(14)
        place = packing.placements[tiles[3].key]
        # the gutter repeats the last column and row of a tile drawn once
        row = (place.y+7-first)*128+place.x//2
        self.assertEqual(data[row:row+3],bytes([0x33,0x33,0x33]))
        with self.assertRaisesRegex(Exception,'slot 15'):
            pack(tiles,slots=[15])

    def test_overflow_is_a_clear_error(self):
        from kitcore.errors import KitError
        from kitcore.texpack import pack
        tiles = [self.tile(128,128,k+1,bits=8,window=True) for k in range(3)]
        with self.assertRaisesRegex(KitError,'do not fit in slots \\[13\\]'):
            pack(tiles,slots=[13])
        packing = pack(tiles,slots=[13,12])
        self.assertEqual(packing.slot_bits,{13:8,12:8})
        many = [self.tile(8,8,k+1) for k in range(16)]
        with self.assertRaisesRegex(KitError,'at most 15'):
            pack([__import__('kitcore.texpack',fromlist=['Tile']).Tile(16,1,4,[[list(range(1,17))]],name='x')],slots=[14])
        self.assertEqual(len({p for b,p in pack(many,slots=[14]).palettes}),2)    # 16 colours: two palettes

    @unittest.skipUnless(PILLOW,'The stall example reads a PNG sheet (Pillow).')
    def test_pack_command_shares_textures_and_palettes(self):
        stall = ROOT/'examples/assets/stall.asset.json'
        with tempfile.TemporaryDirectory() as tmp:
            twin = json.loads(stall.read_text()); twin['name'] = 'twin'
            twin['sheets']['signs']['image'] = str(ROOT/'examples/assets/art/stall_sheet.png')
            Path(tmp,'twin.asset.json').write_text(json.dumps(twin))
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'pack',str(stall),str(Path(tmp,'twin.asset.json')),
                                     str(ROOT/'examples/assets/kiosk.asset.json'),'-o',str(Path(tmp,'out')),'--name','street',
                                     '--slots','12-14'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            out = json.loads(result.stdout)
            plain = json.loads(stall.read_text())
            plain['verification'] = {'required':False,'depth':True,'perspective':True}
            single = build(plain,Path(tmp,'single'),input_path=str(stall))
            self.assertEqual(out['textures']['tiles'],single['textures']['tiles'])    # the twin adds nothing
            manifest = json.loads(Path(tmp,'out/street.pack.json').read_text())
            self.assertEqual([a['name'] for a in manifest['assets']],['stall','twin','kiosk'])
            self.assertEqual(manifest['swatch']['slot'],12)
            self.assertEqual(manifest['assets'][2]['palette']['palettes'],[0])
            self.assertTrue(all(t['slot'] in (12,13,14) for t in manifest['assets'][0]['textures']))
            akr = Path(tmp,'out/street.akr').read_text()
            for line in ('embed ASSET_STALL: Mesh = "stall.bin"','fn street_load() {','const STREET_STALL_LANTERN_FRAMES = 2'):
                self.assertIn(line,akr)
            # the stall and its twin draw the same faces from the same places
            self.assertEqual(Path(tmp,'out/stall.bin').read_bytes(),Path(tmp,'out/twin.bin').read_bytes())
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'pack',str(stall),'-o',str(Path(tmp,'small')),
                                     '--slots','14,13'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            # three 8-bit 128 x 128 textures: an 8-bit slot holds two
            bigs = []
            for k in range(3):
                big = textured({'pattern':'checker','colors':['#000000',f'#0000{k*8+8:02x}'],'size':128,'bits':8})|{'name':f'big{k}'}
                Path(tmp,f'big{k}.asset.json').write_text(json.dumps(big))
                bigs.append(str(Path(tmp,f'big{k}.asset.json')))
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'pack',*bigs,'-o',str(Path(tmp,'over')),
                                     '--slots','14'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertIn('do not fit',json.loads(result.stdout)['errors'][0]['message'])

    def test_build_writes_texture_files_manifest_and_loader(self):
        r = recipe(**{'materials':{'default':{'color':'#a0522d','tag':'wall','texture':{'pattern':'brick','colors':['#a0522d','#d8d0c0']}},
                                   'neon':{'color':'#ff3fa4','class':'emissive'}}}) | {'nodes':[
            {'id':'b','op':'box','size':[1,1,1]},{'id':'n','op':'box','size':[.2,.2,.2],'material':'neon','transform':{'translate':[0,1,0]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            report = build(r,tmp)
            self.assertIn('test.slot14.tex',report['files'])
            self.assertIn('test.tpal',report['files'])
            manifest = json.loads(Path(tmp,'test.materials.json').read_text())
            entry = manifest['textures']['list'][0]
            self.assertEqual((entry['slot'],entry['palette'],entry['repeat'],entry['night']),(14,1,True,'per_colour'))
            self.assertEqual(manifest['textures']['windows'],[entry['window']])
            self.assertEqual(entry['faces'],[[0,12]])
            self.assertFalse(entry['x'] < 16 and entry['y'] < 8,'the swatch block is reserved')
            akr = Path(tmp,'test.akr').read_text()
            load = akr[akr.index('fn asset_test_load()'):]
            self.assertLess(load.index('ASSET_TEST_TEX14'),load.index('ASSET_TEST_SWATCH'),'textures load before the swatch')
            self.assertEqual(Path(tmp,'test.tpal').read_bytes()[:2],b'\0\0')


@unittest.skipUnless(COMPILER.exists() and RUNNER.exists(),'Build Mei for native rendering tests.')
class NativeTextureTests(unittest.TestCase):
    def test_texels_reach_the_screen(self):
        # a 2 x 2 fit texture on a quad facing the camera: each quarter of the quad shows its texel
        colours = ['#ff0000','#00ff00','#0000ff','#ffff00']
        r = textured({'texels':['01','23'],'colors':colours,'projection':'fit'},quad(2,2))
        with tempfile.TemporaryDirectory() as tmp:
            build(r,tmp)
            Path(tmp,'cart.akr').write_text('''cart "Texture test"
import "test.akr"

fn init() { asset_test_load() }

fn draw() {
    cls(0)
    dither(false)
    camera(vec3(0.0, 0.0, -3.0), 0.0)
    mesh(ASSET_TEST)
}
''')
            subprocess.run([str(COMPILER),str(Path(tmp,'cart.akr')),'-o',str(Path(tmp,'cart.mei'))],check=True,capture_output=True)
            subprocess.run([str(RUNNER),str(Path(tmp,'cart.mei')),'--frames','4','--dump',str(Path(tmp,'out.ppm'))],check=True,capture_output=True)
            pixels = Path(tmp,'out.ppm').read_bytes().split(b'\n',3)[3]
            def at(x,y): return tuple(pixels[(y*320+x)*3:(y*320+x)*3+3])
            self.assertEqual([at(130,90),at(190,90),at(130,150),at(190,150)],
                             [(255,0,0),(0,255,0),(0,0,255),(255,255,0)])

    @unittest.skipUnless(PILLOW,'The stall example reads a PNG sheet (Pillow).')
    def test_packed_example_draws_in_depth_and_perspective_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'pack',str(ROOT/'examples/assets/stall.asset.json'),
                                     str(ROOT/'examples/assets/kiosk.asset.json'),'-o',tmp,'--name','street'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            Path(tmp,'cart.akr').write_text('''cart "Pack test"
import "street.akr"
import "depth.akr"

fn init() { street_load() }

fn draw() {
    cls(rgb(24, 28, 36))
    render_depth(true)
    render_perspective(true)
    camera_look(vec3(0.0, 1.5, -4.2), 0.0, -0.05)
    mesh_at(ASSET_STALL, vec3(0.0, 0.0, 0.0), 0.0)
    mesh_at(ASSET_KIOSK, vec3(4.0, 0.0, 2.0), 0.6)
}
''')
            subprocess.run([str(COMPILER),str(Path(tmp,'cart.akr')),'-o',str(Path(tmp,'cart.mei'))],check=True,capture_output=True)
            subprocess.run([str(RUNNER),str(Path(tmp,'cart.mei')),'--frames','4','--dump',str(Path(tmp,'out.ppm')),
                            '--gpu-stats',str(Path(tmp,'stats.csv'))],check=True,capture_output=True)
            from kitcore.native import last_frame_stats
            stats = last_frame_stats(Path(tmp,'stats.csv'))
            self.assertGreater(stats['px_tex'],10000)
            self.assertGreater(stats['px_persp'],0)
            self.assertEqual(stats['tris_dropped'],0)


@unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'The Asset Checker needs NumPy, meic and mei-asset-probe.')
class TextureCheckerTests(unittest.TestCase):
    profile = {'yaw_steps':6,'pitches':[-.3,.2],'distances':[1]}

    def fence(self):
        """A cutout lattice in front of a brick block, in depth mode."""
        return recipe(**{'materials':{
            'wall':{'color':'#a0522d','texture':{'pattern':'brick','colors':['#a0522d','#d8d0c0'],'scale':[.5,.5]}},
            'fence':{'color':'#304050','double_sided':True,'texture':{'pattern':'lattice','colors':['#304050','#000000'],
                     'clear':'#000000','params':{'count':2,'bar':3,'diagonal':True},'projection':'fit'}}},
            'lighting':{'mode':'vertical'},'verification':{'required':True,'depth':True,'perspective':True,**self.profile}}) | {'nodes':[
            {'id':'block','op':'box','size':[1,1,1],'material':'wall','transform':{'translate':[0,.5,.6]}},
            {'id':'fence','op':'mesh','material':'fence','vertices':[[-1,0,-.2],[1,0,-.2],[1,1.2,-.2],[-1,1.2,-.2]],'faces':[[0,1,2,3]]}]}

    def test_cutout_coverage_is_judged_per_texel(self):
        from assetkit import visibility
        report = visibility.verify(self.fence(),compiler=COMPILER,probe=PROBE)
        self.assertTrue(report['ok'],report['totals'])
        self.assertEqual((report['totals']['coverage_errors'],report['totals']['wrong_pixels']),(0,0))
        # the reference really reads the texels: judged as a solid face, the same views fail
        real = visibility.texel_coverage
        try:
            visibility.texel_coverage = lambda np,v,uv,w,xx,yy,inside,area,texture: inside
            solid = visibility.verify(self.fence(),compiler=COMPILER,probe=PROBE)
        finally:
            visibility.texel_coverage = real
        self.assertFalse(solid['ok'])
        self.assertGreater(solid['totals']['coverage_errors'],1000)

    def test_textured_faces_without_holes_are_judged_as_solid_faces(self):
        from assetkit import visibility
        r = textured({'pattern':'brick','colors':['#a0522d','#d8d0c0']},verification={'required':True,**self.profile})
        report = visibility.verify(r,compiler=COMPILER,probe=PROBE)
        self.assertTrue(report['ok'])
        self.assertNotIn('depth_mode',report)
        overlap = textured({'pattern':'brick','colors':['#a0522d','#d8d0c0']}) | {'nodes':[
            {'id':'body','op':'box','size':[2,2,.6]},{'id':'plate','op':'box','size':[1,1,.08],'transform':{'translate':[0,0,-.36]}}]}
        self.assertFalse(visibility.verify(overlap,self.profile,compiler=COMPILER,probe=PROBE)['ok'],
                         'textured faces must not hide ordering errors')


# ---------------------------------------------------------------------------------------------
# One check cart per asset, and the views judged in depth mode (docs/ASSETKIT.md, "Depth mode")

@unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'Needs NumPy, meic and mei-asset-probe.')
class CheckViewTests(unittest.TestCase):
    DEPTH = {'depth':True,'perspective':True}

    def checked(self, r, profile=None):
        from assetkit.visibility import verify
        return verify(r,profile,compiler=COMPILER,probe=PROBE)

    def detailed(self):
        """A body with a plate, a post and a fin: faces seen from few cameras."""
        return recipe() | {'nodes':[
            {'id':'body','op':'box','size':[2,1.2,1]},
            {'id':'plate','op':'box','size':[.6,.4,.06],'transform':{'translate':[0,.2,-.54]}},
            {'id':'post','op':'cylinder','radius':.08,'height':.8,'segments':6,'transform':{'translate':[.7,1.05,0]}},
            {'id':'fin','op':'box','size':[.04,.3,.5],'transform':{'translate':[-.8,.8,0]}}]}

    def test_one_cart_draws_each_camera_as_its_own_cart_did(self):
        # yaw_steps 8 includes the 4 cameras of yaw_steps 4: the same rows, from another table index
        four = self.checked(recipe(),{'yaw_steps':4,'pitches':[-.35],'distances':[1]})
        eight = self.checked(recipe(),{'yaw_steps':8,'pitches':[-.35],'distances':[1]})
        strip = lambda row: {k:v for k,v in row.items() if k != 'index'}
        self.assertEqual([strip(v) for v in four['views']],[strip(v) for v in eight['views'][::2]])

    def test_depth_mode_judges_views_that_draw_every_face(self):
        r = self.detailed()
        full = self.checked(r,{**self.DEPTH,'depth_views':144})
        report = self.checked(r,self.DEPTH)
        selection = report['depth_mode']['view_selection']
        self.assertTrue(report['ok'],report['totals'])
        self.assertEqual(report['profile']['depth_views'],16)
        self.assertEqual(report['totals']['views'],16)
        self.assertEqual(selection['candidates'],144)
        self.assertEqual(selection['faces_drawn_by_views'],selection['faces_drawn_by_sweep'])
        self.assertEqual(report['observed_faces'],full['observed_faces'])
        self.assertEqual(full['totals']['views'],144)
        # the judged views are rows of the full sweep, unchanged
        rows = {v['index']:v for v in full['views']}
        for v in report['views']:
            self.assertEqual({k:x for k,x in v.items() if k not in ('index','sweep_index','image')},
                             {k:x for k,x in rows[v['sweep_index']].items() if k not in ('index','image')})
        # without depth every camera is still judged, and the report is as before
        plain = self.checked(r)
        self.assertEqual(plain['totals']['views'],144)
        self.assertNotIn('depth_views',plain['profile'])
        self.assertTrue(all('sweep_index' not in v for v in plain['views']))

    def test_planted_geometry_faults_fail_without_rendering_help(self):
        # duplicate faces and coplanar overlaps z-fight in the depth buffer: geometry checks
        dup = recipe({'op':'mesh','vertices':[[0,0,0],[2,0,0],[0,2,0]],'faces':[[0,1,2],[0,1,2]]})
        report = self.checked(dup,self.DEPTH)
        self.assertFalse(report['ok'])
        self.assertIn('duplicate_face',report['geometry']['counts'])
        coplanar = recipe({'op':'mesh','vertices':[[0,0,0],[2,0,0],[0,2,0],[.2,.2,0],[1,.2,0],[.2,1,0]],
                           'faces':[[0,1,2],[3,4,5]]})
        report = self.checked(coplanar,self.DEPTH)
        self.assertFalse(report['ok'])
        self.assertIn('coplanar_overlap',report['geometry']['counts'])
        self.assertEqual(report['totals']['wrong_pixels'],0,'the depth test ties them: rendering alone passes them')
        # a T-junction: vertex 4 on the edge 1-2 of the first face, which does not share it
        t = recipe({'op':'mesh','vertices':[[0,0,0],[2,0,0],[2,2,0],[0,2,0],[2,1,0],[3,0,0],[3,2,0]],
                    'faces':[[0,1,2,3],[1,5,4],[4,5,6],[4,6,2]]})
        report = self.checked(t,self.DEPTH)
        self.assertEqual(report['geometry']['counts'],{'t_junction':1})
        self.assertEqual(report['geometry']['findings'],[],'allowed in depth mode: counted, not failing')
        self.assertEqual(report['geometry']['allowed'][0]['examples'][0]['b']['face'] in (0,1),True)
        self.assertNotIn('t_junction',json.dumps(self.checked(t)['geometry']),'without depth the audit is as before')

    @unittest.skipUnless(RUNNER.exists(),'Needs mei-headless.')
    def test_preview_depth_previews_and_checks_as_drawn_with_depth(self):
        # a plate on a body: an ordering-table failure, drawn right by the depth test
        from mei_assets import VerificationFailure
        r = NativeVisibilityGateTests().overlap()
        r['verification'] = {'required':True,'yaw_steps':4,'pitches':[0],'distances':[1]}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(VerificationFailure):
                build(r,tmp,True,COMPILER,RUNNER,probe=PROBE)
            report = build(r,tmp,True,COMPILER,RUNNER,probe=PROBE,drawn={'depth':True,'perspective':True})
            self.assertTrue(report['verification']['ok'])
            self.assertTrue(report['verification']['profile']['depth'])
            for name in ('preview.akr','view_front.akr'):
                self.assertIn('render_depth(true)',(Path(tmp)/name).read_text())
            self.assertTrue(all(v['stats']['px_ztest'] > 0 for v in report['preview']['views']))
        # without the flags an untextured asset's files are as before
        self.assertNotIn('depth',source('test',{'min':[0,0,0],'max':[1,1,1]}))

    def planted(self, r, tamper=None, cutout=None):
        """The Asset Checker in depth mode with the console drawing a tampered mesh (or mask)."""
        from assetkit import visibility
        identity, setup = visibility.identity_mesh, visibility.cutout_setup
        def tampered(*a, **k):
            return tamper(bytearray(identity(*a,**k)))
        def masked(*a, **k):
            faces,textured,cart = setup(*a,**k)
            return faces,textured,(cutout(dict(cart[0])),cart[1])
        try:
            if tamper: visibility.identity_mesh = tampered
            if cutout: visibility.cutout_setup = masked
            return self.checked(r,self.DEPTH)
        finally:
            visibility.identity_mesh, visibility.cutout_setup = identity, setup

    def test_planted_drawing_faults_are_caught_in_the_judged_views(self):
        r = self.detailed()
        mesh,_,_ = compile_recipe(r)
        plate = next(i for i,f in enumerate(mesh.faces) if f.part == 'plate' and f.indices[0] != f.indices[1])
        offset = struct.unpack_from('<I',native_bytes(*compile_recipe(r)[:2],{}),8)[0]
        def face(i):
            return offset+36*i
        def missing(data):
            # the console never draws a plate face (its corners collapsed)
            a = face(plate)
            struct.pack_into('<3H',data,a+4,*([struct.unpack_from('<H',data,a+4)[0]]*3))
            return bytes(data)
        def crack(data):
            # one corner of a plate face moved to another of the plate's vertices: a gap
            a = face(plate)
            corners = struct.unpack_from('<3H',data,a+4)
            others = sorted({v for f in mesh.faces if f.part == 'plate' for v in f.indices}-set(corners))
            struct.pack_into('<H',data,a+8,others[0])
            return bytes(data)
        clean = self.checked(r,self.DEPTH)
        self.assertTrue(clean['ok'])
        for name,tamper in (('missing face',missing),('crack',crack)):
            report = self.planted(r,tamper)
            self.assertFalse(report['ok'],name)
            # where the plate face is missing the body behind it shows: wrong pixels, or nothing: coverage
            self.assertGreater(report['totals']['coverage_errors']+report['totals']['wrong_pixels'],100,name)
            self.assertEqual(report['geometry']['counts'],{})
        # the face the console never draws is a suspect: the reference judges the view the estimate shows it best in
        self.assertEqual(self.planted(r,missing)['depth_mode']['view_selection']['suspect_faces'],[plate])
        # a cutout hole where there should be none: one texel of the fence's mask cleared
        fence = TextureCheckerTests().fence()
        fence['verification'] = {'required':True,**self.DEPTH}
        self.assertTrue(self.checked(fence)['ok'])
        def hole(files):
            name = next(n for n in files if n.startswith('mask'))
            mask = bytearray(files[name])
            k = next(i for i in range(len(mask)//2,len(mask)) if mask[i])
            mask[k] = 0
            files[name] = bytes(mask)
            return files
        report = self.planted(fence,cutout=hole)
        self.assertFalse(report['ok'])
        self.assertGreater(report['totals']['coverage_errors'],0)
        self.assertLessEqual(report['totals']['views'],24)


# ---------------------------------------------------------------------------------------------
# Agent ergonomics: complete failing findings, camera views, flush contacts, tool paths
# (docs/ASSETKIT.md, "Authoring rules", "Reports and repairs", "Camera views", "Native tools")

def png_pixels(path):
    """(width, height, RGB bytes) of a PNG the kit wrote (8-bit RGB, filter 0 on every row)."""
    import zlib
    data = Path(path).read_bytes()
    width,height = struct.unpack('>2I',data[16:24])
    at,chunks = 8,b''
    while at < len(data):
        length = struct.unpack('>I',data[at:at+4])[0]
        if data[at+4:at+8] == b'IDAT': chunks += data[at+8:at+8+length]
        at += 12+length
    raw = zlib.decompress(chunks)
    rows = [raw[y*(width*3+1)+1:(y+1)*(width*3+1)] for y in range(height)]
    return width,height,b''.join(rows)


def crossing_and_flush():
    """A subdivided body crossed by a subdivided bar (hundreds of surface crossings) with a cap
    standing flush on its top (coplanar overlaps)."""
    return recipe() | {'nodes':[
        {'id':'body','op':'box','size':[2,2,2],'modifiers':[{'op':'subdivide','levels':3}]},
        {'id':'bar','op':'box','size':[3,1,1],'modifiers':[{'op':'subdivide','levels':3}],
         'transform':{'rotate':[10,20,30]}},
        {'id':'cap','op':'box','size':[1,.2,1],'transform':{'translate':[0,1.1,0]}}]}


class FindingsTests(unittest.TestCase):
    @unittest.skipUnless(NUMPY,'Needs NumPy.')
    def test_failing_findings_are_complete_and_first_and_allowed_ones_grouped(self):
        from assetkit.geometry_audit import geometry_audit, EXAMPLES
        mesh,_,_ = compile_recipe(crossing_and_flush())
        everything = geometry_audit(mesh)
        crossings,flush = everything['counts']['surface_intersection'],everything['counts']['coplanar_overlap']
        self.assertGreater(crossings,200,'more allowed findings than the old 200-finding limit')
        self.assertGreater(flush,0)
        self.assertEqual(len(everything['findings']),crossings+flush,'without allowed codes every finding fails, in full')
        depth = geometry_audit(mesh,allowed=('surface_intersection','t_junction'))
        self.assertFalse(depth['ok'])
        self.assertEqual(depth['failing'],{'coplanar_overlap':flush})
        self.assertEqual(len(depth['findings']),flush)
        self.assertTrue(all(f['code'] == 'coplanar_overlap' for f in depth['findings']))
        self.assertEqual({tuple(sorted((f['a']['part'],f['b']['part']))) for f in depth['findings']},{('body','cap')})
        self.assertEqual(depth['summary'][0].split(' (')[0],f'coplanar_overlap: {flush} between body and cap')
        self.assertEqual(sum(row['count'] for row in depth['allowed']),crossings)
        self.assertTrue(all(len(row['examples']) <= EXAMPLES and row['code'] == 'surface_intersection' for row in depth['allowed']))
        self.assertEqual({tuple(row['parts']) for row in depth['allowed']},{('bar','body')})
        warn = geometry_audit(mesh,allowed=('duplicate_face','coplanar_overlap','surface_intersection','t_junction'))
        self.assertTrue(warn['ok'])
        self.assertEqual((warn['findings'],warn['summary']),([],[]))

    def test_inspect_warns_of_flush_contacts_before_rendering(self):
        def inspect(r):
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'inspect','-'],
                                    input=json.dumps(r),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            return json.loads(result.stdout)['flush_contacts']
        stacked = recipe() | {'nodes':[{'id':'base','op':'box','size':[2,1,2]},
                                       {'id':'top','op':'box','size':[1,1,1],'transform':{'translate':[0,1,0]}}]}
        flush = inspect(stacked)
        if not NUMPY:
            self.assertFalse(flush['checked'])
            return
        self.assertTrue(flush['checked'])
        self.assertEqual(flush['by_code'],{'coplanar_overlap':flush['count']})
        self.assertIn('between base and top',flush['summary'][0])
        self.assertIn('1-2 cm',flush['hint'])
        stacked['nodes'][1]['transform']['translate'] = [0,.99,0]          # sunk 1 cm: no contact
        self.assertEqual(inspect(stacked)['count'],0)
        stacked['nodes'][1]['transform']['translate'] = [0,1,0]
        stacked['nodes'][1]['open'] = ['bottom']                             # or the hidden face opened
        self.assertEqual(inspect(stacked)['count'],0)


class CameraParsingTests(unittest.TestCase):
    def test_cameras_from_eye_and_target_or_yaw_and_pitch(self):
        from assetkit.preview import parse_camera, cameras_file, look
        view = parse_camera('door=0,1.6,-4:0,1.6,0',0)
        self.assertEqual((view['name'],view['eye'],view['yaw'],view['pitch']),('door',[0,1.6,-4],0.0,0.0))
        yaw,pitch = look([0,0,0],[1,0,0])
        self.assertAlmostEqual(yaw,math.pi/2)                    # toward +X: positive yaw
        yaw,pitch = look([0,0,0],[0,1,1])
        self.assertAlmostEqual(pitch,math.pi/4)                  # up: positive pitch
        view = parse_camera('3,2,1@90,-30',4)
        self.assertEqual(view['name'],'camera5')
        self.assertAlmostEqual(view['yaw'],math.pi/2)
        self.assertAlmostEqual(view['pitch'],-math.pi/6)
        views = cameras_file([{'name':'a','eye':[0,1,-3],'target':[0,1,0]},{'name':'b','eye':[0,1,-3],'yaw':0,'pitch':0}])
        self.assertEqual([v['name'] for v in views],['a','b'])
        for bad in ('x=1,2:3,4,5','x=1,2,3','Bad=1,2,3:4,5,6','x=0,0,0:0,0,0','x=1,2,3@0,120'):
            with self.subTest(bad=bad), self.assertRaises(AssetError):
                parse_camera(bad,0)
        with self.assertRaises(AssetError):
            cameras_file([{'eye':[0,1,-3],'look':[0,0,0]}])

    def test_closeups_follow_a_long_axis(self):
        from assetkit.preview import closeups
        train = closeups({'min':[-12.5,0,-1.5],'max':[12.5,3.5,1.5]})
        self.assertEqual([v['name'] for v in train],['eye_level','closeup_1','closeup_2','closeup_3','closeup_4'])
        self.assertAlmostEqual(train[0]['eye'][1],1.6)
        self.assertLess(train[0]['eye'][2],-1.5)                  # in front, on the -Z side
        self.assertLess(train[1]['eye'][0],train[4]['eye'][0])    # left to right along X
        self.assertTrue(all(v['eye'][2] < 0 for v in train[1:]))
        along_z = closeups({'min':[-1,0,-10],'max':[1,2,10]})
        self.assertTrue(all(v['eye'][0] > 1 for v in along_z[1:]),'a Z-long asset is seen from +X')
        self.assertEqual([v['name'] for v in closeups({'min':[-1,0,-1],'max':[1,2,1]})],['eye_level'])

    def test_tool_paths_from_options_build_dir_environment_and_b(self):
        import argparse
        from mei_assets import tool_paths, require_tools
        args = lambda **k: argparse.Namespace(**{'compiler':None,'runner':None,'probe':None,'build_dir':None,**k})
        paths = lambda a, env: {k:v[0] for k,v in tool_paths(a,env).items()}
        self.assertEqual(paths(args(),{}),{'compiler':ROOT/'build/meic','runner':ROOT/'build/mei-headless',
                                           'probe':ROOT/'build/mei-asset-probe'})
        self.assertEqual(paths(args(),{'B':'build-x'})['probe'],ROOT/'build-x/mei-asset-probe')
        env = {'B':'build-x','MEIC':'/tmp/a/meic','RUN':'/tmp/a/run','PROBE':'/tmp/a/probe'}
        self.assertEqual(paths(args(),env),{'compiler':Path('/tmp/a/meic').resolve(),'runner':Path('/tmp/a/run').resolve(),
                                            'probe':Path('/tmp/a/probe').resolve()})
        self.assertEqual(paths(args(build_dir=Path('/tmp/b')),env)['compiler'],Path('/tmp/b/meic').resolve())
        self.assertEqual(paths(args(build_dir=Path('/tmp/b'),probe=Path('/tmp/c/p')),env)['probe'],Path('/tmp/c/p').resolve())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssetError) as caught:
                require_tools(tool_paths(args(build_dir=Path(tmp)),{}),['compiler','probe'])
        message = str(caught.exception)
        self.assertIn(f'Missing meic in {Path(tmp).resolve()}',message)
        self.assertIn('from --build-dir',message)
        self.assertIn('make B=',message)
        self.assertIn('--build-dir DIR',message)
        self.assertIn('MEIC',message)

    def test_missing_tools_are_named_with_their_directory_on_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k:v for k,v in os.environ.items() if k not in ('MEIC','RUN','PROBE','B')}
            env['B'] = tmp
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'verify','-'],input=json.dumps(recipe()),
                                    capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,1)
            error = json.loads(result.stdout)['errors'][0]
            self.assertEqual(error['path'],'/arguments/tools')
            self.assertIn(f'in {Path(tmp).resolve()} (the compiler, from B={tmp})',error['message'])
            self.assertIn('mei-asset-probe',error['message'])
            self.assertNotIn('mei-headless',error['message'],'verify needs no runner')


@unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'Needs NumPy, meic and mei-asset-probe.')
class VerdictTests(unittest.TestCase):
    profile = {'yaw_steps':4,'pitches':[0],'distances':[1]}

    def test_the_verdict_and_the_geometry_block_agree(self):
        from assetkit.visibility import verify
        depth = {**self.profile,'depth':True,'perspective':True}
        crossing = recipe() | {'nodes':[{'id':'body','op':'box','size':[2,2,2]},
                                        {'id':'bar','op':'box','size':[3,.5,.5],'transform':{'rotate':[0,0,20]}}]}
        report = verify(crossing,depth,compiler=COMPILER,probe=PROBE)
        self.assertTrue(report['ok'])
        self.assertTrue(report['geometry']['ok'],'allowed crossings do not fail the geometry block')
        self.assertEqual(report['failures'],[])
        self.assertTrue(report['verdict'].startswith('PASS (depth mode)'))
        self.assertIn('surface_intersection',report['verdict'])
        self.assertTrue(report['allowed'][0].startswith('surface_intersection: '))
        self.assertIn('between bar and body',report['allowed'][0])
        self.assertEqual(list(report)[:4],['ok','verdict','failures','allowed'],'the verdict leads the report')
        report = verify(crossing_and_flush(),depth,compiler=COMPILER,probe=PROBE)
        self.assertFalse(report['ok'])
        self.assertFalse(report['geometry']['ok'])
        self.assertTrue(report['verdict'].startswith('FAIL (depth mode)'))
        self.assertTrue(report['failures'][0].startswith('geometry: coplanar_overlap: '))
        self.assertIn('between body and cap',report['failures'][0])
        # --geometry warn: the geometry block passes and says which codes it allowed
        report = verify(crossing_and_flush(),{**depth,'geometry':'warn'},compiler=COMPILER,probe=PROBE)
        self.assertTrue(report['geometry']['ok'])
        self.assertIn('coplanar_overlap',report['geometry']['allowed_codes'])


@unittest.skipUnless(COMPILER.exists() and RUNNER.exists(),'Needs meic and mei-headless.')
class CameraViewTests(unittest.TestCase):
    def test_camera_views_render_at_world_scale_with_their_cost(self):
        from assetkit.preview import parse_camera
        r = recipe() | {'nodes':[{'id':'car','op':'box','size':[20,3,3],'transform':{'translate':[0,1.5,0]}},
                                 {'id':'sign','op':'box','size':[.4,.3,.05],'transform':{'translate':[9,2.5,-1.52]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            shots = {'cameras':[parse_camera('sign=9,2.5,-2.5:9,2.5,-1.5',0)],'parts':['sign'],'closeups':True,'upscale':2}
            report = build(r,tmp,True,COMPILER,RUNNER,shots=shots)
            self.assertEqual(png_pixels(Path(tmp)/'contact.png')[:2],(960,480),'the contact sheet is as before')
            cameras = report['preview']['cameras']
            names = [v['view'] for v in cameras['views']]
            self.assertEqual(names,['eye_level','closeup_1','closeup_2','closeup_3','closeup_4','part_sign','sign'])
            width,height,pixels = png_pixels(Path(tmp)/'camera_sign.png')
            self.assertEqual((width,height),(640,480))
            self.assertEqual(png_pixels(Path(tmp)/'cameras.png')[:2],(1280,480*4))
            # one metre from the sign it fills the middle of the view
            middle = pixels[(240*640+320)*3:(240*640+320)*3+3]
            self.assertNotEqual(tuple(middle),(24,28,36))
            for view in cameras['views']:
                cost = view['cost']
                self.assertGreater(cost['asset_gpu_cycles'],0,view['view'])
                self.assertEqual(cost['gpu_cycles']-cost['asset_gpu_cycles'],cameras['baseline']['gpu_cycles'])
                self.assertEqual(cost['gpu_frame_percent'],round(100*cost['gpu_cycles']/cameras['budgets']['gpu'],1))
            self.assertEqual(cameras['budgets'],{'cpu':1000000,'gpu':2000000})
            self.assertIn('cost',report['preview']['views'][0])
            # the camera cart draws the mesh as placed: mesh_at at the origin, yaw 0
            self.assertIn('mesh_at(ASSET_TEST, vec3(0.0, 0.0, 0.0), 0.0)',(Path(tmp)/'camera_sign.akr').read_text())
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(AssetError,'No part'):
            build(r,tmp,True,COMPILER,RUNNER,shots={'parts':['wheel']})

    def test_preview_cli_takes_cameras_and_the_build_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            cams = Path(tmp)/'shots.json'
            cams.write_text(json.dumps([{'name':'low','eye':[0,.2,-4],'target':[0,0,0]}]))
            env = {k:v for k,v in os.environ.items() if k not in ('MEIC','RUN','PROBE','B')}
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'preview','-','-o',str(Path(tmp)/'out'),
                                     '--build-dir',str(COMPILER.parent),'--runner',str(RUNNER),'--cameras',str(cams),
                                     '--camera','high=0,4,-4@0,-45','--upscale','3'],
                                    input=json.dumps(recipe()),capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,0,result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual([v['view'] for v in report['preview']['cameras']['views']],['low','high'])
            self.assertEqual(png_pixels(Path(tmp)/'out'/'camera_high.png')[:2],(960,720))


@unittest.skipUnless(NUMPY and COMPILER.exists() and RUNNER.exists() and PROBE.exists(),
                     'Needs NumPy, meic, mei-headless and mei-asset-probe.')
class FailedPreviewTests(unittest.TestCase):
    def test_a_failed_verification_keeps_renders_marked_as_failing(self):
        from mei_assets import VerificationFailure
        r = crossing_and_flush()
        r['verification'] = {'required':True,'depth':True,'perspective':True,'yaw_steps':4,'pitches':[0],'distances':[1]}
        with tempfile.TemporaryDirectory() as tmp:
            build(recipe(),tmp)
            previous = (Path(tmp)/'test.bin').read_bytes()
            with self.assertRaises(VerificationFailure) as caught:
                build(r,tmp,True,COMPILER,RUNNER,probe=PROBE,shots={'closeups':True,'upscale':1})
            message = str(caught.exception)
            self.assertIn('coplanar_overlap',message)
            self.assertIn('between body and cap',message)
            self.assertIn('verification-failed/preview/contact.png',message)
            self.assertEqual((Path(tmp)/'test.bin').read_bytes(),previous,'nothing exported')
            renders = Path(tmp)/'verification-failed'/'preview'
            for name in ('contact.png','view_front.png','cameras.png','camera_eye_level.png'):
                self.assertTrue((renders/name).is_file(),name)
            self.assertFalse((Path(tmp)/'contact.png').exists())
            failed = json.loads((Path(tmp)/'verification.failed.json').read_text())
            self.assertTrue(failed['preview']['failing'])
            self.assertTrue(failed['preview']['cameras']['failing'])
            # the banner: red text near the top left of every render
            width,height,pixels = png_pixels(renders/'view_front.png')
            banner = [pixels[(y*width+x)*3:(y*width+x)*3+3] for y in range(18,30) for x in range(8,160)]
            self.assertTrue(any(p[0] > 200 and p[1] < 100 and p[2] < 100 for p in banner),'the VERIFICATION FAILED banner')
            # the CLI leads its failure output with the errors. (It stops this recipe before rendering, for
            # its flush cap: FeedbackTests. Crossing parts without the depth buffer fail in the views.)
            crossing = crossing_and_flush()
            crossing['nodes'].pop()
            crossing['verification'] = {'required':True,'yaw_steps':4,'pitches':[0],'distances':[1]}
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'preview','-','-o',tmp,
                                     '--compiler',str(COMPILER),'--runner',str(RUNNER),'--probe',str(PROBE)],
                                    input=json.dumps(crossing),capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertEqual(list(json.loads(result.stdout))[:3],['ok','errors','verdict'])
            self.assertTrue((renders/'contact.png').is_file())


@unittest.skipUnless(COMPILER.exists() and RUNNER.exists(),'Needs meic and mei-headless.')
class ConventionTests(unittest.TestCase):
    """The orientation conventions of docs/ASSETKIT.md's authoring rules, checked on renders."""
    GRID = {'texels':['00001111']*4+['22223333']*4,'colors':['#ff0000','#00ff00','#0000ff','#ffffff']}
    COLOURS = {(255,0,0):'red',(0,255,0):'green',(0,0,255):'blue',(255,255,255):'white',(24,28,36):'none'}

    def look(self, nodes, views, points, materials=None):
        """{view: {label: colour name}} at the given screen points of each camera view."""
        from assetkit.preview import camera
        r = recipe(None,lighting={'bake':False},materials=materials or {'default':{'color':'#808080'}}) | {'nodes':nodes}
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            cams = [camera(name,eye,target) for name,(eye,target) in views.items()]
            build(r,tmp,True,COMPILER,RUNNER,shots={'cameras':cams,'upscale':1})
            for name in views:
                width,_,pixels = png_pixels(Path(tmp)/f'camera_{name}.png')
                out[name] = {}
                for label,(x,y) in points.items():
                    p = tuple(pixels[(y*width+x)*3:(y*width+x)*3+3])
                    best = min(self.COLOURS,key=lambda c:sum((a-b)**2 for a,b in zip(c,p)))
                    out[name][label] = self.COLOURS[best] if sum((a-b)**2 for a,b in zip(best,p)) < 3600 else 'grey'
        return out

    FRONT = {'front':([0,0,-3],[0,0,0])}
    QUADRANTS = {'TL':(140,100),'TR':(180,100),'BL':(140,140),'BR':(180,140)}
    CENTRE = {'C':(160,120)}

    def textured(self, projection, **extra):
        return {'default':{'color':'#808080','texture':{**self.GRID,'projection':projection,**extra}}}

    def test_box_sides_and_facing(self):
        views = {'front':([0,0,-3],[0,0,0]),'back':([0,0,3],[0,0,0])}
        seen = self.look([{'id':'b','op':'box','size':[1,1,1],'open':['back']}],views,self.CENTRE)
        self.assertEqual((seen['front']['C'],seen['back']['C']),('none','grey'),'back is -Z: the side the front camera sees')
        seen = self.look([{'id':'b','op':'box','size':[1,1,1],'open':['front']}],views,self.CENTRE)
        self.assertEqual((seen['front']['C'],seen['back']['C']),('grey','none'))

    def test_rotation_direction(self):
        mats = {'default':{'color':'#808080'},'red':{'color':'#ff0000'}}
        def marker(at, rotate):
            return [{'id':'g','op':'group','transform':{'rotate':rotate},'children':[
                {'id':'core','op':'box','size':[.4,.4,.4]},
                {'id':'m','op':'box','size':[.3,.3,.3],'material':'red','transform':{'translate':at}}]}]
        places = {'up':(160,60),'down':(160,180),'left':(100,120),'right':(220,120)}
        def where(seen):
            return [k for k,v in seen.items() if v == 'red']
        from assetkit.preview import camera
        top = {'top':([0,3,0],[0,0,.0001])}            # looking down: +X right, +Z up the screen
        self.assertEqual(where(self.look(marker([1,0,0],[0,0,0]),top,places,mats)['top']),['right'])
        self.assertEqual(where(self.look(marker([0,0,1],[0,0,0]),top,places,mats)['top']),['up'])
        # [0, 90, 0]: +X to -Z, clockwise in the top view
        self.assertEqual(where(self.look(marker([1,0,0],[0,90,0]),top,places,mats)['top']),['down'])
        # [0, 0, 90]: +X to +Y, counterclockwise in the front view
        self.assertEqual(where(self.look(marker([1,0,0],[0,0,90]),self.FRONT,places,mats)['front']),['up'])
        # [90, 0, 0]: +Y to +Z; the right camera (on +X) has +Z on its right
        self.assertEqual(where(self.look(marker([0,1,0],[90,0,0]),{'right':([3,0,0],[0,0,0])},places,mats)['right']),['right'])

    def test_winding_and_fit(self):
        quad = {'id':'q','op':'mesh','vertices':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],'faces':[[3,2,1,0]]}
        seen = self.look([quad],self.FRONT,self.QUADRANTS,self.textured('fit'))['front']
        self.assertEqual(seen,{'TL':'red','TR':'green','BL':'blue','BR':'white'})
        seen = self.look([{**quad,'faces':[[0,1,2,3]]}],self.FRONT,self.CENTRE)['front']
        self.assertEqual(seen['C'],'none','listed counterclockwise on screen: facing away, culled')
        # on a triangle, fit spans the bounding rectangle: the corner outside is not drawn
        tri = {'id':'t','op':'extrude','points':[[-1,-1],[1,-1],[-1,1]],'depth':.2}
        seen = self.look([tri],self.FRONT,{'TL':(103,84),'TR':(190,90),'BL':(130,150),'BR':(185,150)},self.textured('fit'))['front']
        self.assertEqual(seen,{'TL':'red','TR':'none','BL':'blue','BR':'white'})

    def test_projection_origins(self):
        quad = {'id':'q','op':'mesh','vertices':[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],'faces':[[3,2,1,0]]}
        # planar: a repeat's top-left corner at the primitive's origin
        seen = self.look([quad],self.FRONT,self.QUADRANTS,self.textured('planar',scale=[2,2]))['front']
        self.assertEqual(seen,{'TL':'white','TR':'blue','BL':'green','BR':'red'})
        # box: every side read from outside
        views = {'front':([0,0,-3],[0,0,0]),'right':([3,0,0],[0,0,0]),'top':([0,3,0],[0,0,.0001]),'back':([0,0,3],[0,0,0])}
        seen = self.look([{'id':'b','op':'box','size':[1,1,1]}],views,self.QUADRANTS,self.textured('box',offset=[.5,.5]))
        for name in views:
            self.assertEqual(seen[name],{'TL':'red','TR':'green','BL':'blue','BR':'white'},name)
        # cylindrical: u 0 on the -Z meridian, growing toward +X; v 0 at y 0, growing down
        drum = {'id':'c','op':'cylinder','radius':.5,'height':1,'segments':24,'caps':False}
        seen = self.look([drum],self.FRONT,self.QUADRANTS,self.textured('cylindrical',scale=[math.pi,1]))['front']
        self.assertEqual(seen,{'TL':'white','TR':'blue','BL':'green','BR':'red'})
        # disc about Y: seen from above, u 0 at -X and v 0 at +Z
        disc = {'id':'c','op':'cylinder','radius':1,'height':.1,'segments':24}
        seen = self.look([disc],{'top':([0,3,0],[0,0,.0001])},self.QUADRANTS,self.textured('disc'))['top']
        self.assertEqual(seen,{'TL':'red','TR':'green','BL':'blue','BR':'white'})

def gltf_png_pixels(data):
    """(width, height, RGBA rows) of an 8-bit RGBA PNG whose rows all use filter 0, as the glTF
    export writes them."""
    import zlib
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    at, idat, head = 8, b'', None
    while at < len(data):
        size, kind = struct.unpack_from('>I4s',data,at)
        body = data[at+8:at+8+size]
        if kind == b'IHDR': head = struct.unpack('>2I5B',body)
        if kind == b'IDAT': idat += body
        at += 12+size
    width, height, depth, colour = head[:4]
    assert (depth,colour) == (8,6)
    raw = zlib.decompress(idat)
    rows = []
    for y in range(height):
        line = raw[y*(1+4*width):(y+1)*(1+4*width)]
        assert line[0] == 0
        rows.append([tuple(line[1+4*x:5+4*x]) for x in range(width)])
    return width, height, rows


class GltfExportTests(unittest.TestCase):
    """`export`: the asset as glTF 2.0, drawn as Mei draws it (assetkit/gltf.py)."""

    def exported(self, r, folder=None):
        from assetkit import gltf
        mesh, materials, _ = compile_recipe(r, folder)
        document, blob, summary = gltf.export(mesh, materials, r, r['name'])
        # through the .glb container and back, as a viewer reads it
        document, blob = gltf.read_glb(gltf.glb_bytes(document, blob))
        return mesh, document, blob, summary

    def read(self, document, blob, index):
        """An accessor's values, as tuples of its type's width."""
        acc = document['accessors'][index]
        view = document['bufferViews'][acc['bufferView']]
        width = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[acc['type']]
        code = {5126:'f',5123:'H',5125:'I'}[acc['componentType']]
        values = struct.unpack_from(f'<{acc["count"]*width}{code}',blob,view['byteOffset']+acc.get('byteOffset',0))
        return [values[k:k+width] for k in range(0,len(values),width)]

    def triangles(self, document, blob):
        """[(material, [(position, colour, uv or None) per corner])] of every triangle."""
        out = []
        for prim in document['meshes'][0]['primitives']:
            attrs = prim['attributes']
            pos = self.read(document,blob,attrs['POSITION'])
            col = self.read(document,blob,attrs['COLOR_0'])
            uv = self.read(document,blob,attrs['TEXCOORD_0']) if 'TEXCOORD_0' in attrs else None
            idx = [i for (i,) in self.read(document,blob,prim['indices'])]
            for k in range(0,len(idx),3):
                out.append((prim['material'],[(pos[i],col[i],uv[i] if uv else None) for i in idx[k:k+3]]))
        return out

    def check_structure(self, document, blob):
        self.assertEqual(document['asset']['version'],'2.0')
        self.assertIn('KHR_materials_unlit',document['extensionsUsed'])
        self.assertEqual(document['buffers'],[{'byteLength':len(blob)}])
        for view in document['bufferViews']:
            self.assertEqual(view['byteOffset']%4,0)
            self.assertLessEqual(view['byteOffset']+view['byteLength'],len(blob))
        for acc in document['accessors']:
            view = document['bufferViews'][acc['bufferView']]
            size = acc['count']*{'SCALAR':1,'VEC2':2,'VEC3':3}[acc['type']]*(2 if acc['componentType'] == 5123 else 4)
            self.assertLessEqual(size,view['byteLength'])
        for prim in document['meshes'][0]['primitives']:
            count = document['accessors'][prim['attributes']['POSITION']]['count']
            for name in prim['attributes']:
                self.assertEqual(document['accessors'][prim['attributes'][name]]['count'],count)
            indices = self.read(document,blob,prim['indices'])
            self.assertEqual(len(indices)%3,0)
            self.assertTrue(all(0 <= i < count for (i,) in indices))
            positions = self.read(document,blob,prim['attributes']['POSITION'])
            acc = document['accessors'][prim['attributes']['POSITION']]
            for k in range(3):
                self.assertEqual(acc['min'][k],min(p[k] for p in positions))
                self.assertEqual(acc['max'][k],max(p[k] for p in positions))
        for mat in document['materials']:
            self.assertIn('KHR_materials_unlit',mat['extensions'])
        for sampler in document.get('samplers',[]):
            self.assertEqual((sampler['magFilter'],sampler['minFilter']),(9728,9728))
        for image in document.get('images',[]):
            view = document['bufferViews'][image['bufferView']]
            gltf_png_pixels(blob[view['byteOffset']:view['byteOffset']+view['byteLength']])

    def test_untextured_asset_structure_and_colours(self):
        from assetkit.gltf import linear, decode_native
        r = json.loads((ROOT/'examples/assets/robot.asset.json').read_text())
        mesh, document, blob, summary = self.exported(r)
        self.check_structure(document,blob)
        self.assertEqual(summary['triangles'],len(mesh.faces))
        self.assertNotIn('images',document)
        # every corner's colour is the native vertex colour, as linear light
        materials = {'default':{'color':'#c4cad4'},**r['materials']}
        _, faces, _ = decode_native(native_bytes(mesh,materials,r.get('lighting',{})))
        native = {tuple(round(linear(((c >> s) & 255)/255),5) for s in (0,8,16)) for f in faces for c in f['colours']}
        exported = {tuple(round(c,5) for c in corner[1]) for _,tri in self.triangles(document,blob) for corner in tri}
        self.assertEqual(exported,native)

    def test_handedness_nothing_is_mirrored(self):
        """Mei's world is left-handed (camera_look: looking along +Z, +X is to the right). The
        export negates Z: the front (-Z in the kit) faces glTF's +Z, +X stays to the right, and
        front faces wind counter-clockwise seen from outside."""
        r = recipe(None,**{'materials':{'mark':{'color':'#ff0000'},'nose':{'color':'#00ff00'}}}) | {'nodes':[
            {'id':'body','op':'box','size':[2,2,2]},
            {'id':'right_mark','op':'box','size':[.2,.2,.2],'material':'mark','transform':{'translate':[1.5,0,0]}},
            {'id':'front_nose','op':'cone','radius':.3,'height':.6,'segments':6,'material':'nose',
             'transform':{'rotate':[-90,0,0],'translate':[0,0,-1.3]}}]}
        mesh, document, blob, _ = self.exported(r)
        tris = self.triangles(document,blob)
        positions = {tuple(round(c,4) for c in corner[0]) for _,tri in tris for corner in tri}
        self.assertEqual(positions,{(round(x,4),round(y,4),round(-z,4)) for x,y,z in mesh.vertices})
        mark = document['materials'].index(next(m for m in document['materials'] if m['name'] == 'mark'))
        self.assertTrue(all(c[0][0] > 1 for m,tri in tris if m == mark for c in tri))
        # the nose's tip, the kit's front at z -1.6, is glTF's +z 1.6
        self.assertAlmostEqual(max(p[2] for p in positions),1.6,places=3)
        # every triangle of the closed body faces outward with counter-clockwise winding
        body = [tri for m,tri in tris if document['materials'][m]['name'] == 'default']
        self.assertEqual(len(body),12)
        for tri in body:
            a,b,c = (corner[0] for corner in tri)
            centre = [sum(p[k] for p in (a,b,c))/3 for k in range(3)]
            self.assertGreater(dot(cross(sub(b,a),sub(c,a)),centre),0)

    def texture_recipe(self):
        """A repeating 8 x 8 texel grid of 8 colours on a wall spanning 3 x 1.5 repeats, and a
        cutout drawn once on a double-sided emissive sign."""
        grid = [''.join('0123456789abcdef'[(x+2*y)%8] for x in range(8)) for y in range(8)]
        colours = ['#202020','#e04040','#40e040','#4040e0','#e0e040','#40e0e0','#e040e0','#f0f0f0']
        hole = ['0000','0110','0110','0000']
        return recipe(None,**{'materials':{
            'wall':{'color':'#808080','texture':{'texels':grid,'colors':colours,'projection':'planar','scale':[1,1],
                                                 'offset':[.25,0]}},
            'sign':{'color':'#c08040','class':'emissive','double_sided':True,
                    'texture':{'texels':hole,'colors':['#000000','#ffcc00'],'clear':'#000000','projection':'fit'}}},
            'verification':DEPTH_POLICY,'lighting':{'direction':[0.3,0.5,-1]}}) | {'nodes':[
            quad(3.0,1.5) | {'material':'wall'},
            quad(1.0,1.0,-0.5) | {'id':'sign','material':'sign','transform':{'translate':[0,2,0]}}]}

    def test_textures_and_uvs_round_trip(self):
        """Each triangle's texels at points inside it, read back from the exported PNG through
        its UVs and sampler, are the texels the compiled face samples there; the tint is the bake's."""
        from assetkit.gltf import linear
        from assetkit.textures import rgb_of
        r = self.texture_recipe()
        mesh, document, blob, summary = self.exported(r)
        self.check_structure(document,blob)
        images = {}
        for k,image in enumerate(document['images']):
            view = document['bufferViews'][image['bufferView']]
            images[k] = gltf_png_pixels(blob[view['byteOffset']:view['byteOffset']+view['byteLength']])
        by_name = {m['name']:m for m in document['materials']}
        self.assertEqual(by_name['sign']['alphaMode'],'MASK')
        self.assertTrue(by_name['sign']['doubleSided'])
        self.assertEqual(by_name['sign']['emissiveFactor'],[1,1,1])
        self.assertNotIn('alphaMode',by_name['wall'])
        self.assertNotIn('doubleSided',by_name['wall'])
        wraps = {by_name[n]['name']:document['samplers'][document['textures'][by_name[n]['pbrMetallicRoughness']['baseColorTexture']['index']]['sampler']]['wrapS']
                 for n in ('wall','sign')}
        self.assertEqual(wraps,{'wall':10497,'sign':33071})
        textures = mesh.textures['textures']
        # the compiled faces by their glTF positions
        compiled = {}
        for face in mesh.faces:
            key = frozenset(tuple(round(c,4) for c in (x,y,-z)) for x,y,z in (mesh.vertices[i] for i in face.indices))
            compiled[key] = face
        checked = {'wall':0,'sign':0}
        for m,tri in self.triangles(document,blob):
            mat = document['materials'][m]
            face = compiled[frozenset(tuple(round(c,4) for c in corner[0]) for corner in tri)]
            tex = textures[face.material]
            width, height, rows = images[document['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']]
            at = {tuple(round(c,4) for c in (x,y,-z)):t for (x,y,z),t in
                  zip((mesh.vertices[i] for i in face.indices),face.texcoords)}
            texels = [at[tuple(round(c,4) for c in corner[0])] for corner in tri]
            for weights in ((.6,.25,.15),(.15,.6,.25),(.25,.15,.6),(.34,.33,.33)):
                u = sum(w*c[2][0] for w,c in zip(weights,tri))
                v = sum(w*c[2][1] for w,c in zip(weights,tri))
                if wraps[mat['name']] == 10497: u, v = u % 1, v % 1
                exported = rows[int(v*height)][int(u*width)]
                tu = sum(w*t[0] for w,t in zip(weights,texels))
                tv = sum(w*t[1] for w,t in zip(weights,texels))
                c15 = tex.tile.frames[0][int(tv) % tex.height][int(tu) % tex.width]
                self.assertEqual(exported,(0,0,0,0) if c15 is None else (*rgb_of(c15),255))
            checked[mat['name']] += 1
            # the corners' colours: the bake as a tint (128 = 1), emissive never shaded
            for corner in tri:
                if mat['name'] == 'sign': self.assertEqual(corner[1],(1.0,1.0,1.0))
                else: self.assertTrue(all(0 < c < 1 for c in corner[1]))
        self.assertEqual(checked,{'wall':sum(f.material == 'wall' for f in mesh.faces),'sign':2})
        # the sign's hole is transparent and the rest opaque
        sign_image = images[document['textures'][by_name['sign']['pbrMetallicRoughness']['baseColorTexture']['index']]['source']]
        self.assertEqual((sign_image[0],sign_image[1]),(5,5))       # 4 x 4 and its gutter
        self.assertEqual([px[3] for px in sign_image[2][1]],[0,255,255,0,0])     # '0110' and the gutter
        self.assertEqual(summary['dropped_frames'],[])
        self.assertAlmostEqual(linear(1.0),1.0)

    @unittest.skipUnless(PILLOW,'the stall reads its sheet with Pillow')
    def test_stall_cli_glb_and_gltf(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'export',
                                     str(ROOT/'examples/assets/stall.asset.json'),'-o',tmp],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual((report['triangles'],report['images'],report['hidden_faces']),(144,8,0))
            self.assertEqual(report['dropped_frames'],[{'material':'lantern','frames':2,'exported':0,'dropped':1}])
            from assetkit import gltf
            document, blob = gltf.read_glb((Path(tmp)/'stall.glb').read_bytes())
            self.check_structure(document,blob)
            masks = sorted(m['name'] for m in document['materials'] if m.get('alphaMode') == 'MASK')
            self.assertEqual(masks,['emblem','screen'])
            result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),'export',
                                     str(ROOT/'examples/assets/stall.asset.json'),'-o',tmp,'--format','gltf'],
                                    capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            text = json.loads((Path(tmp)/'stall.gltf').read_text())
            import base64
            uri = text['buffers'][0].pop('uri')
            self.assertEqual(base64.b64decode(uri.split(',',1)[1]),blob)
            self.assertEqual(text,document)


# Feedback from agents who built models with the kit: the flush check in build and preview, close
# parallel faces, more in inspect, clearer errors, axis names for open sides
# (docs/ASSETKIT.md, "Quick reference", "Authoring rules", "Commands")

def kit(*args, stdin=None):
    """(exit code, JSON result) of tools/mei_assets.py."""
    result = subprocess.run([sys.executable,str(ROOT/'tools/mei_assets.py'),*map(str,args)],
                            input=json.dumps(stdin) if stdin is not None else None,capture_output=True,text=True)
    return result.returncode,json.loads(result.stdout)


def stacked():
    """A box standing flush on a larger one: a coplanar overlap, back to back."""
    return recipe() | {'nodes':[{'id':'base','op':'box','size':[2,1,2]},
                                {'id':'top','op':'box','size':[1,1,1],'transform':{'translate':[0,1,0]}}]}


def sign_on_board(gap):
    """A sign panel whose front face stands gap in front of its board's (both face -Z)."""
    return recipe() | {'nodes':[{'id':'board','op':'box','size':[2,1,.1]},
                                {'id':'panel','op':'box','size':[1.6,.7,.02],'transform':{'translate':[0,0,-.05-gap+.01]}}]}


class FeedbackTests(unittest.TestCase):
    @unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'Needs NumPy, meic and mei-asset-probe.')
    def test_build_and_preview_stop_before_rendering_on_flush_contacts_when_checked(self):
        r = stacked() | {'verification':{'required':True,'depth':True,'perspective':True}}
        with tempfile.TemporaryDirectory() as tmp:
            for command in ('build','preview'):
                code,out = kit(command,'-','-o',tmp,'--compiler',COMPILER,'--runner',RUNNER,'--probe',PROBE,stdin=r)
                self.assertEqual(code,1)
                self.assertEqual(list(out)[:3],['ok','errors','flush_contacts'])
                message = out['errors'][0]['message']
                self.assertEqual(out['errors'][0]['path'],'/verification')
                self.assertTrue(message.startswith('Stopped before rendering: '),message)
                self.assertIn('coplanar_overlap: 4 between base and top',message)
                # the smaller part, which way and about how far
                self.assertIn('sink top about 0.02 along -Y into base',message)
                self.assertIn('"open": ["bottom"]',message)
                self.assertEqual(list(Path(tmp).iterdir()),[],'nothing written, nothing rendered')
            # without the depth buffer sinking would make the parts cross: open the face instead
            r['verification'] = {'required':True}
            code,out = kit('build','-','-o',tmp,'--compiler',COMPILER,'--probe',PROBE,stdin=r)
            self.assertIn('which fails without the depth buffer',out['errors'][0]['message'])

    @unittest.skipUnless(NUMPY,'Needs NumPy.')
    def test_build_reports_flush_contacts_when_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            code,out = kit('build','-','-o',tmp,stdin=stacked())
            self.assertEqual(code,0,out)
            self.assertEqual(out['flush_contacts']['count'],4)
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_text())['flush_contacts'],out['flush_contacts'])
            r = stacked() | {'nodes':stacked()['nodes'][:1]}
            code,out = kit('build','-','-o',tmp,stdin=r)
            self.assertEqual(out['flush_contacts']['count'],0)

    @unittest.skipUnless(NUMPY,'Needs NumPy.')
    def test_close_parallel_faces_are_a_warning(self):
        from assetkit.geometry_audit import close_faces, CLOSE_GAP
        self.assertEqual(CLOSE_GAP,.03)
        close = close_faces(compile_recipe(sign_on_board(.01))[0])
        self.assertEqual(close['count'],4)                          # 2 x 2 triangles of the two front faces
        self.assertEqual((close['pairs'][0]['front'],close['pairs'][0]['behind']),('panel','board'))
        self.assertAlmostEqual(close['pairs'][0]['gap_min'],.01,places=4)
        self.assertTrue(close['summary'][0].startswith('close_faces: 4 between panel and board: panel\'s faces 10.0 mm in front of'),
                        close['summary'][0])
        self.assertAlmostEqual(close['pairs'][0]['fights_from']['grazing'],2.9,places=1)
        self.assertEqual(close_faces(compile_recipe(sign_on_board(.04))[0])['count'],0,'4 cm is clear')
        # in one plane is a coplanar overlap, not this; back to back (a plate under a box) neither
        flush = recipe() | {'nodes':[{'id':'board','op':'box','size':[2,1,.1]},
                                     {'id':'panel','op':'box','size':[1,.5,.05],'transform':{'translate':[0,0,-.025]}}]}
        self.assertEqual(close_faces(compile_recipe(flush)[0])['count'],0)
        under = recipe() | {'nodes':[{'id':'box','op':'box','size':[1,1,1]},
                                     {'id':'plate','op':'box','size':[1,.01,1],'open':['-y','-x','+x','-z','+z'],
                                      'transform':{'translate':[0,-.51,0]}}]}
        self.assertEqual(close_faces(compile_recipe(under)[0])['count'],0)
        code,out = kit('inspect','-',stdin=sign_on_board(.01))
        self.assertEqual((code,out['ok'],out['close_faces']['count']),(0,True,4))
        self.assertIn('3 cm proud',out['close_faces']['hint'])

    @unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'Needs NumPy, meic and mei-asset-probe.')
    def test_verify_warns_of_close_parallel_faces_and_passes(self):
        from assetkit.visibility import verify
        report = verify(sign_on_board(.01),{'yaw_steps':4,'pitches':[0],'distances':[1],'depth':True,'perspective':True},
                        compiler=COMPILER,probe=PROBE)
        self.assertTrue(report['ok'],report['failures'])
        self.assertEqual(list(report)[:5],['ok','verdict','failures','allowed','warnings'])
        self.assertTrue(report['warnings'][0].startswith('close_faces: 4 between panel and board'))
        self.assertEqual(report['geometry']['close_faces']['count'],4)

    def test_inspect_reports_in_full_over_budget(self):
        r = recipe({'id':'ball','op':'sphere','radius':1,'rings':8,'segments':16},budget={'triangles':100,'vertices':50})
        with self.assertRaises(AssetError):
            compile_recipe(r)
        code,out = kit('inspect','-',stdin=r)
        self.assertEqual((code,out['ok']),(0,True))
        breaches = [w for w in out['warnings'] if w['code'] == 'over_budget']
        self.assertEqual([(w['key'],w['count'],w['budget']) for w in breaches],[('vertices',114,50),('triangles',224,100)])
        self.assertEqual(out['parts'][0]['triangles'],224)
        self.assertEqual(kit('build','-','-o',tempfile.gettempdir()+'/never-written',stdin=r)[1]['errors'][0]['path'],
                         '/budget/vertices')

    def test_inspect_lists_texture_windows_and_names_them_when_over_seven(self):
        def material(k):
            return {'color':'#808080','texture':{'pattern':'checker','colors':['#000000',f'#{k:02x}{k:02x}{k:02x}']}}
        r = recipe() | {'materials':{f'm{k}':material(k*16) for k in range(8)} | {'twin':material(0)},
                        'nodes':[{'id':f'b{k}','op':'box','size':[1,1,1],'material':f'm{k}',
                                  'transform':{'translate':[2*k,0,0]}} for k in range(7)] +
                                [{'id':'twin','op':'box','size':[1,1,1],'material':'twin','transform':{'translate':[0,2,0]}}]}
        code,out = kit('inspect','-',stdin=r)
        windows = out['texture_windows']
        self.assertEqual((windows['used'],windows['max']),(7,7))
        self.assertEqual(windows['windows'][0],{'window':1,'texture':"pattern 'checker'",'size':[16,16],'bits':4,
                                                'materials':['m0','twin']},'one tile, one window, both materials')
        r['nodes'].append({'id':'b7','op':'box','size':[1,1,1],'material':'m7','transform':{'translate':[0,4,0]}})
        code,out = kit('inspect','-',stdin=r)
        message = out['errors'][0]['message']
        self.assertIn('8 different repeating textures',message)
        self.assertIn("1: pattern 'checker' 16 x 16 (m0, twin)",message)
        self.assertIn('8: pattern \'checker\' 16 x 16 (m7)',message)

    def test_inspect_warns_of_mirror_copies_and_parts_below_ground(self):
        def warnings(r):
            return {w['code']:w for w in kit('inspect','-',stdin=r)[1]['warnings']}
        centred = recipe({'id':'post','op':'box','size':[.2,1,.2],'modifiers':[{'op':'mirror','axis':'x'}]})
        w = warnings(centred)
        self.assertEqual(w['mirror_coincides']['part'],'post')
        self.assertEqual(w['mirror_coincides']['path'],'/nodes/0/modifiers/0')
        self.assertIn('below_ground',w)
        self.assertEqual(w['below_ground']['parts'],['post'])
        across = recipe({'id':'arm','op':'box','size':[1,1,1],'transform':{'translate':[0,.5,0]},
                         'modifiers':[{'op':'mirror','axis':'x','offset':.2}]})
        w = warnings(across)
        self.assertIn('mirror_overlaps',w)
        self.assertNotIn('below_ground',w,'the transform lifts it after the modifier')
        touching = recipe({'id':'wing','op':'group','children':[
            {'id':'half','op':'box','size':[1,.2,1],'transform':{'translate':[.5,1,0]}}],
            'modifiers':[{'op':'mirror','axis':'x'}]})
        w = warnings(touching)
        self.assertEqual(w['mirror_touches']['count'],2)
        self.assertEqual(w['mirror_touches']['part'],'wing')
        touching['nodes'][0]['children'][0]['open'] = ['-x']
        self.assertEqual(set(warnings(touching)),set(),'the two open halves close each other')
        # these are inspect's: build's report and --strict are as before
        _,_,report = compile_recipe(centred)
        self.assertNotIn('mirror_coincides',{w['code'] for w in report['warnings']})

    def test_texture_splits_no_longer_collapse_and_the_error_says_why(self):
        from assetkit import textures
        wall = recipe({'id':'wall','op':'mesh','material':'brick','faces':[[3,2,1,0]],
                       'vertices':[[-3.3,0,0],[-2.1,0,0],[-2.1,2,0],[-3.3,2,0]]},
                      materials={'brick':{'color':'#884422','texture':{'pattern':'brick','colors':['#884422','#dddddd'],
                                                                      'projection':'planar','scale':[.1,.1]}}})
        mesh,_,report = compile_recipe(wall)            # a corner 2e-13 texels off a cut line made a sliver
        self.assertGreater(report['textures']['split_faces'],0)
        saved = textures.ON_LINE
        textures.ON_LINE = -1                           # as before: cut there
        try:
            with self.assertRaises(AssetError) as caught:
                compile_recipe(wall)
        finally:
            textures.ON_LINE = saved
        self.assertEqual(caught.exception.path,'/materials/brick/texture/scale')
        for text in ("material 'brick'","pattern 'brick'",'16 x 16 texels','scale [0.1, 0.1]','power-of-two'):
            self.assertIn(text,str(caught.exception))

    def test_planarity_error_states_deviation_and_tolerance(self):
        bent = recipe({'id':'leaf','op':'mesh','vertices':[[0,0,0],[1,0,0],[1,1,.1],[0,1,0]],'faces':[[0,1,2,3]]})
        with self.assertRaises(AssetError) as caught:
            compile_recipe(bent)
        message = str(caught.exception)
        self.assertIn('0.0499 units off the plane',message)
        self.assertIn('the tolerance is 1.42e-06 units',message)

    def test_errors_name_the_nodes_on_their_path(self):
        from mei_assets import node_of
        r = recipe() | {'nodes':[{'id':'body','op':'box','size':[1,1,1]},
                                 {'op':'group','children':[{'id':'arm','op':'box','size':[1,1,0]}]}],
                        'prototypes':{'wheel':{'id':'rim','op':'box','size':[1,1,1]}},
                        'lod':{'levels':[{'distance':10,'nodes':[{'id':'lump','op':'box','size':[1,1,1]}]}]}}
        self.assertEqual(node_of(r,'/nodes/1/children/0/size/2'),'group_1/arm')
        self.assertEqual(node_of(r,'/prototypes/wheel/size'),'prototype wheel: rim')
        self.assertEqual(node_of(r,'/lod/levels/0/nodes/0/size'),'lod level 1: lump')
        self.assertIsNone(node_of(r,'/budget/triangles'))
        code,out = kit('validate','-',stdin=r)
        self.assertEqual(out['errors'][0]['path'],'/nodes/1/children/0/size/2')
        self.assertEqual(out['errors'][0]['node'],'group_1/arm')

    def test_open_sides_by_axis(self):
        names = ['back','top','left']
        for axes in (['-z','+y','-x'],['back','+y','-x']):
            a = native_bytes(*compile_recipe(recipe({'id':'b','op':'box','size':[1,2,3],'open':names}))[:2],{})
            b = native_bytes(*compile_recipe(recipe({'id':'b','op':'box','size':[1,2,3],'open':axes}))[:2],{})
            self.assertEqual(a,b)
        for side,axis in (('front','+z'),('right','+x'),('bottom','-y')):
            a = native_bytes(*compile_recipe(recipe({'id':'b','op':'box','size':[1,2,3],'open':[side]}))[:2],{})
            b = native_bytes(*compile_recipe(recipe({'id':'b','op':'box','size':[1,2,3],'open':[axis]}))[:2],{})
            self.assertEqual(a,b)
        with self.assertRaises(AssetError) as caught:
            compile_recipe(recipe({'id':'b','op':'box','size':[1,1,1],'open':['back','-z']}))
        self.assertIn('Name each side once',str(caught.exception))
        with self.assertRaises(AssetError):
            compile_recipe(recipe({'id':'b','op':'box','size':[1,1,1],'open':['z']}))


FD_MATERIALS = {'wall':{'color':'#c8b8a0'},'sign':{'color':'#d04030'},'roof':{'color':'#404040'},
                'poster':{'color':'#2040d0','texture':{'projection':'fit','colors':['#000000','#ffffff'],
                                                       'texels':['0111','0000']}}}


def fd_recipe(*nodes, **extra):
    return recipe(**{'materials':dict(FD_MATERIALS),**extra}) | {'nodes':list(nodes)}


def side_materials(mesh):
    """{(axis, sign) of the face normal: set of materials}."""
    out = {}
    for f in mesh.faces:
        a,b,c = (mesh.vertices[i] for i in f.indices)
        n = cross(sub(b,a),sub(c,a))
        k = max(range(3),key=lambda i: abs(n[i]))
        out.setdefault((k,1 if n[k] > 0 else -1),set()).add(f.material)
    return out


class FaceMaterialTests(unittest.TestCase):
    def test_box_faces_by_name_and_axis_add_no_triangles(self):
        plain,_,base = compile_recipe(fd_recipe({'id':'b','op':'box','size':[2,1,1],'material':'wall'}))
        for faces in ({'top':'roof','back':'sign'},{'+y':'roof','-z':'sign'}):
            mesh,_,rep = compile_recipe(fd_recipe({'id':'b','op':'box','size':[2,1,1],'material':'wall','faces':faces}))
            self.assertEqual((rep['triangles'],rep['vertices']),(base['triangles'],base['vertices']))
            sides = side_materials(mesh)
            self.assertEqual(sides[(1,1)],{'roof'})
            self.assertEqual(sides[(2,-1)],{'sign'})
            self.assertEqual(sides[(0,1)],{'wall'})
            self.assertEqual(rep['face_maps'],[{'part':'b','path':'/nodes/0','sides':{'back':'sign','top':'roof'},
                                                'triangles':{'back':2,'top':2}}])
            self.assertEqual(rep['parts'][0]['boundary_edges'],0)
        self.assertNotIn('face_maps',base)

    def test_caps_and_sides(self):
        for op,extra in (('cylinder',{'radius':.5,'height':1}),('lathe',{'profile':[[.5,0],[.4,1]]}),
                         ('loft',{'sections':[{'y':0,'points':[[-1,-1],[1,-1],[1,1],[-1,1]]},
                                              {'y':1,'points':[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]]}]})):
            with self.subTest(op=op):
                node = {'id':'c','op':op,'material':'wall','faces':{'top':'roof','-y':'sign'},**extra}
                mesh,_,rep = compile_recipe(fd_recipe(node))
                _,_,base = compile_recipe(fd_recipe({k:v for k,v in node.items() if k != 'faces'}))
                self.assertEqual(rep['triangles'],base['triangles'])
                sides = side_materials(mesh)
                self.assertEqual(sides[(1,1)],{'roof'})
                self.assertEqual(sides[(1,-1)],{'sign'})
        mesh,_,_ = compile_recipe(fd_recipe({'id':'c','op':'cone','radius':.5,'height':1,'faces':{'side':'sign','bottom':'roof'}}))
        self.assertEqual({f.material for f in mesh.faces},{'sign','roof'})
        mesh,_,_ = compile_recipe(fd_recipe({'id':'e','op':'extrude','points':[[0,0],[1,0],[0,1]],'depth':1,
                                             'material':'wall','faces':{'+z':'sign'}}))
        self.assertEqual(side_materials(mesh)[(2,1)],{'sign'})
        self.assertEqual(side_materials(mesh)[(2,-1)],{'wall'})

    def test_errors_name_the_side_and_why(self):
        cases = [
            ({'op':'box','size':[1,1,1],'open':['front'],'faces':{'+z':'sign'}},'/nodes/0/faces/+z','is open'),
            ({'op':'box','size':[1,1,1],'faces':{'top':'sign','+y':'roof'}},'/nodes/0/faces/+y','named twice'),
            ({'op':'box','size':[1,1,1],'faces':{'top':'nope'}},'/nodes/0/faces/top',"Unknown material 'nope'"),
            ({'op':'cone','radius':1,'height':1,'faces':{'top':'sign'}},'/nodes/0/faces/top','A cone has no top cap'),
            ({'op':'cylinder','radius':1,'height':1,'caps':False,'faces':{'bottom':'sign'}},'/nodes/0/faces/bottom','caps is false'),
            ({'op':'lathe','profile':[[1,0],[0,1]],'faces':{'top':'sign'}},'/nodes/0/faces/top','ends in a point'),
        ]
        for node,path,text in cases:
            with self.subTest(text=text):
                with self.assertRaises(AssetError) as caught:
                    compile_recipe(fd_recipe(node))
                self.assertEqual(caught.exception.path,path)
                self.assertIn(text,str(caught.exception))
        with self.assertRaises(AssetError) as caught:      # schema: a sphere has no sides
            compile_recipe(fd_recipe({'op':'sphere','radius':1,'faces':{'top':'sign'}}))
        self.assertEqual(caught.exception.path,'/nodes/0/faces')

    def test_instance_material_keeps_face_maps_and_decals(self):
        r = fd_recipe({'id':'one','op':'instance','ref':'stall','material':'wall'},
                      prototypes={'stall':{'op':'box','size':[2,1,1],'material':'roof','faces':{'back':'sign'},
                                           'decals':[{'face':'left','material':'poster','size':[.4,.4]}]}})
        mesh,_,_ = compile_recipe(r)
        sides = side_materials(mesh)
        self.assertEqual(sides[(2,-1)],{'sign'})
        self.assertEqual(sides[(0,-1)],{'wall','poster'})
        self.assertEqual(sides[(1,1)],{'wall'})

    def test_texture_windows_count_face_materials(self):
        mats = {f'm{k}':{'color':'#808080','texture':{'pattern':'checker','colors':['#000000',f'#{32*k+16:02x}0000']}}
                for k in range(8)}
        node = {'id':'b','op':'box','size':[1,1,1],'material':'m0',
                'faces':dict(zip(('top','bottom','left','right','back'),('m1','m2','m3','m4','m5')))}
        r = recipe(node,materials=mats)
        code,out = kit('inspect','-',stdin=r)
        self.assertEqual(code,0,out)
        self.assertEqual(out['texture_windows']['used'],6)
        r['nodes'] = [node,{'id':'c','op':'box','size':[1,1,1],'material':'m6','faces':{'top':'m7'},
                            'transform':{'translate':[2,0,0]}}]
        code,out = kit('inspect','-',stdin=r)
        self.assertEqual(code,1)
        self.assertIn('8 different repeating textures',out['errors'][0]['message'])


class DecalTests(unittest.TestCase):
    def wall(self, *decals, **extra):
        return fd_recipe({'id':'wall','op':'box','size':[4,3,.2],'material':'wall','open':['bottom'],
                          'decals':list(decals),**extra})

    def test_each_decal_adds_8_triangles_and_4_vertices_and_keeps_the_part_closed(self):
        _,_,base = compile_recipe(fd_recipe({'id':'b','op':'box','size':[4,3,1]}))
        for count in (1,2,5):
            decals = [{'face':'back','material':'poster','size':[.5,.5],'at':[-1.6+.8*k,0]} for k in range(count)]
            mesh,_,rep = compile_recipe(fd_recipe({'id':'b','op':'box','size':[4,3,1],'decals':decals}))
            self.assertEqual(rep['triangles'],base['triangles']+8*count)
            self.assertEqual(rep['vertices'],base['vertices']+4*count)
            part = rep['parts'][0]
            self.assertEqual((part['boundary_edges'],part['nonmanifold_edges'],part['inconsistent_edges']),(0,0,0))
            self.assertGreater(volume(mesh),0)
            self.assertEqual([d['added_triangles'] for d in rep['decals']],[8]*count)
        for node in ({'op':'cylinder','radius':1,'height':1,'segments':16},
                     {'op':'extrude','points':[[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]],'depth':.5},
                     {'op':'lathe','profile':[[1,0],[.6,1]]}):
            with self.subTest(op=node['op']):
                face = 'back' if node['op'] == 'extrude' else 'top'
                at = [.5,1.4] if node['op'] == 'extrude' else [0,0]
                _,_,a = compile_recipe(fd_recipe(node))
                _,_,b = compile_recipe(fd_recipe({**node,'decals':[{'face':face,'material':'poster','size':[.4,.3],'at':at}]}))
                self.assertEqual(b['triangles'],a['triangles']+8)
                self.assertEqual(b['parts'][0]['boundary_edges'],0)

    def test_decal_lies_in_the_face_with_its_texture_once_over_it(self):
        mesh,_,rep = compile_recipe(self.wall({'id':'poster','face':'-z','material':'poster','size':[.8,1.2],'at':[.8,.1]}))
        faces = [f for f in mesh.faces if f.decal == 'wall/poster']
        self.assertEqual(len(faces),2)
        self.assertTrue(all(f.material == 'poster' for f in faces))
        points = {tuple(round(c,4) for c in mesh.vertices[i]) for f in faces for i in f.indices}
        # the wall's back face is at z -0.1; "right" on it is +X, up +Y, from the box's centre
        self.assertEqual(points,{(x,y,-.1) for x in (.4,1.2) for y in (-.5,.7)})
        # u runs right, v down, the whole texture (4 x 2 texels) once
        uv = {tuple(round(c,4) for c in mesh.vertices[i]):t for f in faces for i,t in zip(f.indices,f.texcoords)}
        self.assertEqual(uv[(.4,.7,-.1)],(0,0))
        self.assertEqual(uv[(1.2,.7,-.1)],(4,0))
        self.assertEqual(uv[(1.2,-.5,-.1)],(4,2))
        decal = rep['decals'][0]
        self.assertEqual((decal['id'],decal['part'],decal['face'],decal['material'],decal['triangles']),
                         ('wall/poster','wall','back','poster',2))
        self.assertEqual(decal['normal'],[0,0,-1])
        self.assertEqual(decal['path'],'/nodes/0/decals/0')

    def test_texture_rotate_applies_to_a_decal(self):
        r = self.wall({'id':'p','face':'back','material':'poster','size':[1,2]})
        r['materials']['poster'] = {'color':'#000000','texture':{**FD_MATERIALS['poster']['texture'],'rotate':90}}
        mesh,_,_ = compile_recipe(r)
        uv = {tuple(round(c,4) for c in mesh.vertices[i]):t for f in mesh.faces if f.decal for i,t in zip(f.indices,f.texcoords)}
        self.assertEqual(set(uv.values()),{(0,0),(4,0),(0,2),(4,2)})
        self.assertEqual(uv[(-.5,1,-.1)],(0,2))         # top-left shows the texture's bottom-left

    @unittest.skipUnless(NUMPY,'The geometry audit needs NumPy.')
    def test_no_flush_contacts_or_t_junctions(self):
        from assetkit.geometry_audit import geometry_audit
        r = self.wall(*[{'face':'back','material':'poster','size':[.6,.6],'at':[x,y]} for x in (-1,0,1) for y in (-.6,.6)],
                      {'face':'left','material':'sign','size':[.1,.5]})
        mesh,_,_ = compile_recipe(r)
        audit = geometry_audit(mesh,t_junctions=True)
        self.assertTrue(audit['ok'],audit['summary'])
        code,out = kit('inspect','-',stdin=r)
        self.assertEqual(code,0)
        self.assertEqual(out['flush_contacts']['count'],0)
        self.assertEqual(out['close_faces']['pairs'],[])
        self.assertEqual(len(out['decals']),7)

    def test_errors_name_the_decal_and_why(self):
        cases = [
            ({'face':'back','material':'poster','size':[1,1],'at':[1.8,0]},'/nodes/0/decals/0',
             "its right edge is 0.3 past the face's right edge"),
            ({'face':'back','material':'poster','size':[4,1]},'/nodes/0/decals/0','within 0.001 of the face'),
            ({'face':'bottom','material':'poster','size':[1,.1]},'/nodes/0/decals/0/face','is open'),
            ({'face':'back','material':'nope','size':[1,1]},'/nodes/0/decals/0/material',"Unknown material 'nope'"),
            ({'face':'back','material':'sign','size':[1,1]},None,None),
            ({'face':2,'material':'sign','size':[1,1]},'/nodes/0/decals/0/face','Name the side'),
            ({'face':'z','material':'sign','size':[1,1]},'/nodes/0/decals/0/face',"A box has no side 'z'"),
        ]
        for decal,path,text in cases:
            with self.subTest(decal=decal):
                if path is None:
                    compile_recipe(self.wall(decal))
                    continue
                with self.assertRaises(AssetError) as caught:
                    compile_recipe(self.wall(decal))
                self.assertEqual(caught.exception.path,path)
                self.assertIn(text,str(caught.exception))
        with self.assertRaises(AssetError) as caught:
            compile_recipe(self.wall({'face':'back','material':'sign','size':[1,1]},
                                     {'face':'back','material':'sign','size':[1,1],'at':[.5,.5]}))
        self.assertEqual(caught.exception.path,'/nodes/0/decals/1')
        self.assertIn("overlaps decal 'decal_0'",str(caught.exception))
        r = self.wall({'face':'back','material':'checks','size':[1,1]})
        r['materials']['checks'] = {'color':'#000000','texture':{'pattern':'checker','colors':['#000000','#ffffff']}}
        with self.assertRaises(AssetError) as caught:
            compile_recipe(r)
        self.assertIn('"projection": "fit"',str(caught.exception))
        for node,text in (({'op':'cylinder','radius':1,'height':1},'curved'),
                          ({'op':'extrude','points':[[0,0],[1,0],[0,1]],'depth':1},'several faces')):
            with self.assertRaises(AssetError) as caught:
                compile_recipe(fd_recipe({**node,'decals':[{'face':'side','material':'sign','size':[.1,.1]}]}))
            self.assertIn(text,str(caught.exception))
        # an L-shaped outline: the decal must not cross its notch
        with self.assertRaises(AssetError) as caught:
            compile_recipe(fd_recipe({'op':'extrude','points':[[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]],'depth':1,
                                      'decals':[{'face':'back','material':'sign','size':[.6,.6],'at':[1.3,1.3]}]}))
        self.assertIn("crosses the face's outline",str(caught.exception))

    def test_mesh_polygon_decal_and_modifiers_copy_it(self):
        node = {'id':'m','op':'mesh','vertices':[[0,0,0],[0,1,0],[1,1,0],[1,0,0]],'faces':[[0,1,2,3]],
                'decals':[{'id':'d','face':0,'material':'sign','size':[.5,.5],'at':[.5,.5]}]}
        _,_,rep = compile_recipe(fd_recipe(node))
        self.assertEqual(rep['triangles'],10)
        with self.assertRaises(AssetError) as caught:
            compile_recipe(fd_recipe({**node,'decals':[{'face':1,'material':'sign','size':[.5,.5]}]}))
        self.assertIn('polygon by its index, 0-0',str(caught.exception))
        node = {'id':'b','op':'box','size':[1,1,1],'decals':[{'id':'d','face':'back','material':'sign','size':[.4,.4]}],
                'modifiers':[{'op':'array','count':3,'step':[2,0,0]}]}
        _,_,rep = compile_recipe(fd_recipe(node))
        self.assertEqual(rep['triangles'],3*20)
        self.assertEqual((rep['decals'][0]['triangles'],rep['decals'][0]['added_triangles']),(6,24))
        self.assertAlmostEqual(rep['decals'][0]['bounds']['min'][0],-.2,4)
        self.assertAlmostEqual(rep['decals'][0]['bounds']['max'][0],4.2,4)

    def test_preview_part_frames_a_decal_face_on(self):
        from assetkit.preview import part_camera
        _,_,rep = compile_recipe(self.wall({'id':'poster','face':'back','material':'poster','size':[.8,1.2],'at':[.8,.1]},
                                           transform={'translate':[0,1.5,0]}))
        view = part_camera(rep['parts'],'wall/poster',rep['decals'])
        self.assertTrue(view['name'].startswith('decal_wall_poster'))
        self.assertLess(view['eye'][2],-1)                 # on the -Z side, looking at the face
        self.assertAlmostEqual(view['eye'][0],.8,3)
        self.assertAlmostEqual(view['eye'][1],1.6,3)
        with self.assertRaises(AssetError) as caught:
            part_camera(rep['parts'],'wall/nope',rep['decals'])
        self.assertIn('Decals: wall/poster',str(caught.exception))

    @unittest.skipUnless(NUMPY and COMPILER.exists() and PROBE.exists(),'Needs NumPy, meic and mei-asset-probe.')
    def test_baked_decal_passes_both_modes_where_a_proud_quad_fails_without_depth(self):
        from assetkit.visibility import verify
        profile = {'yaw_steps':8,'pitches':[-.35,0],'distances':[1]}
        baked = fd_recipe({'id':'wall','op':'box','size':[4,3,.2],'material':'wall','open':['bottom'],
                           'decals':[{'id':'poster','face':'back','material':'sign','size':[.8,1.2],'at':[.8,.1]}]})
        proud = fd_recipe({'id':'wall','op':'box','size':[4,3,.2],'material':'wall','open':['bottom']},
                          {'id':'poster','op':'mesh','material':'sign','vertices':[[-.4,.6,0],[.4,.6,0],[.4,-.6,0],[-.4,-.6,0]],
                           'faces':[[0,1,2,3]],'transform':{'translate':[.8,.1,-.135]}})
        for depth in (False,True):
            report = verify(baked,{**profile,'depth':depth},compiler=COMPILER,probe=PROBE)
            self.assertTrue(report['ok'],report['failures'])
            self.assertEqual(report['geometry']['counts'],{})
        report = verify(proud,profile,compiler=COMPILER,probe=PROBE)
        self.assertFalse(report['ok'])
        self.assertGreater(report['totals']['wrong_pixels'],0)


if __name__ == '__main__':
    unittest.main()
