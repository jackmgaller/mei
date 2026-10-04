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
        for path in (ROOT/'examples/assets').glob('*.json'):
            with self.subTest(path=path.name):
                _,_,report = compile_recipe(json.loads(path.read_text()))
                self.assertEqual(report['warnings'],[])


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
        for path in (ROOT/'examples/assets').glob('*.json'):
            with self.subTest(asset=path.name), tempfile.TemporaryDirectory() as tmp:
                report = build(json.loads(path.read_text()),tmp,True,COMPILER,RUNNER,probe=PROBE)
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

    def checked(self,r,**kw):
        from assetkit.visibility import verify
        return verify(r,self.profile,compiler=COMPILER,probe=PROBE,**kw)

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
        for overrides in ({'yaw_steps':0},{'pitches':[]},{'distances':[float('nan')]},{'geometry':'ignore'}):
            with self.assertRaises(AssetError):verify(recipe(),overrides,compiler=COMPILER,probe=PROBE)


if __name__ == '__main__':
    unittest.main()
