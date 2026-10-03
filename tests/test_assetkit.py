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
from assetkit.compiler import compile_recipe, native_bytes, import_obj, obj_text
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
