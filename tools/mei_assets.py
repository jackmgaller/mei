#!/usr/bin/env python3
"""Mei Asset Kit: agent-first procedural 3D modeling and native render feedback.

Run `python3 tools/mei_assets.py schema` for the complete recipe contract, or
read docs/ASSETKIT.md. All command results and errors are JSON on stdout.
"""
import json
from pathlib import Path
import sys

from kitcore import jsonio, output as staged
from kitcore.cli import parser_class
from assetkit.compiler import (AssetError, compile_recipe, native_bytes,
                               editor_project, obj_text, import_obj, import_source,
                               material_manifest, palette_bytes, SWATCH)
from assetkit.preview import source, render
from assetkit.schema import SCHEMA

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT/'examples'/'assets'
MAX_INPUT = jsonio.MAX_INPUT
output = jsonio.output
write_new = jsonio.write_new


def load(path):
    return jsonio.load(path,AssetError)


def artifacts(recipe, mesh, materials, report):
    name = recipe['name']
    binary = native_bytes(mesh,materials,recipe.get('lighting',{}))
    import hashlib
    report['mesh_sha256'] = hashlib.sha256(binary).hexdigest()
    files = {
        name+'.bin':binary,
        name+'.akr':import_source(name,mesh).encode(),
        name+'.asset.json':(json.dumps(recipe,indent=2,allow_nan=False)+'\n').encode(),
        name+'.model.json':(json.dumps(editor_project(mesh,materials,name,recipe.get('lighting',{})),indent=2)+'\n').encode(),
        name+'.obj':('mtllib '+name+'.mtl\n'+obj_text(mesh,materials)).encode(),
        name+'.mtl':''.join('newmtl '+key+'\nKd '+' '.join(f'{int(mat["color"][i:i+2],16)/255:.6f}' for i in (1,3,5))+'\n\n' for key,mat in sorted(materials.items())).encode(),
        'preview.akr':source(name,report['bounds'],load=bool(mesh.palette)).encode(),
        'report.json':(json.dumps(report,indent=2)+'\n').encode(),
    }
    # Every build has a manifest; only palette-backed meshes have palettes and a swatch, so
    # the files legacy recipes always had are unchanged.
    files[name+'.materials.json'] = (json.dumps(material_manifest(mesh,materials,recipe),indent=2)+'\n').encode()
    if mesh.palette:
        files[name+'.pal'] = palette_bytes(mesh)
        files[name+'.swatch'] = SWATCH
    # Levels of detail: a mesh each, embedded after level 0 (they share its palette entries).
    for k,(level,_) in enumerate(mesh.levels or [],1):
        files[f'{name}.lod{k}.bin'] = native_bytes(level,materials,recipe.get('lighting',{}))
        files[name+'.akr'] += f'embed ASSET_{name.upper()}_LOD{k}: Mesh = "{name}.lod{k}.bin"\n'.encode()
    return files


class VerificationFailure(AssetError):
    def __init__(self, report):
        super().__init__('/verification','Export blocked by verification. Inspect the face/camera witnesses in verification.failed.json or run verify for a diagnostic sweep.')
        self.report=report


def build(recipe, directory, preview=False, compiler=None, runner=None, input_path=None, verification=False, probe=None):
    mesh,materials,report = compile_recipe(recipe)
    files = artifacts(recipe,mesh,materials,report)
    directory = Path(directory).resolve()
    if input_path and input_path != '-':
        source_path = Path(input_path).resolve()
        if any(directory/name == source_path for name in files):
            raise AssetError('/output','Output would overwrite the source recipe. Use a separate output directory.')
    # Complete validation and serialization before replacing any generated outputs.
    # Stage preview too, so compiler/render failures leave the previous build intact.
    with staged.staging(directory,'.mei-assets-') as stage:
        for name,data in files.items(): (stage/name).write_bytes(data)
        policy=recipe.get('verification')
        if verification or (policy is not None and policy.get('required',True)):
            from assetkit.visibility import verify
            checked=verify(recipe,directory=stage,compiler=compiler,probe=probe)
            if not checked['ok']:
                failure=directory/'verification.failed.json'
                if input_path and input_path!='-' and Path(input_path).resolve()==failure:
                    raise AssetError('/output','Failure report would overwrite the source recipe. Use a separate output directory.')
                if checked['images']:
                    images_dir=directory/'verification-failed'
                    images_dir.mkdir(exist_ok=True)
                    for filename in checked['images']:(stage/filename).replace(images_dir/filename)
                    for row in checked['views']:
                        if 'image' in row:row['image']='verification-failed/'+row['image']
                    checked['images']=['verification-failed/'+name for name in checked['images']]
                failure.write_text(json.dumps(checked,indent=2)+'\n')
                raise VerificationFailure(checked)
            report['verification']=checked
        if preview:
            report['preview'] = render(stage,recipe['name'],report['bounds'],compiler,runner,bool(mesh.palette))
            report['preview']['contact'] = str(directory/'contact.png')
        (stage/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        generated = sorted(p.name for p in stage.iterdir())
        if input_path and input_path != '-' and any(directory/name == Path(input_path).resolve() for name in generated):
            raise AssetError('/output','Generated preview would overwrite the source recipe. Use a separate output directory.')
        staged.commit(stage,directory)
    report['output'] = str(directory)
    report['files'] = generated
    return report


ArgumentParser = parser_class(AssetError)


def parser():
    p = ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('schema',help='Print the complete JSON Schema; no file access needed.')
    init = sub.add_parser('init',help='Write an editable example recipe (never overwrite by default).')
    init.add_argument('output')
    init.add_argument('--example',choices=['robot','vessel','cottage','kiosk'],default='robot')
    init.add_argument('--force',action='store_true')
    for name in ('validate','inspect','build','preview','verify'):
        cmd = sub.add_parser(name,help={'validate':'Validate schema, topology and Mei budgets.',
                                      'inspect':'Return bounds, costs and diagnostics per named part.',
                                      'build':'Export native meshes, Akari import, OBJ and editor project.',
                                      'preview':'Build and render six views using the actual Mei GPU.',
                                      'verify':'Audit geometry and native triangle visibility across a camera sweep.'}[name])
        cmd.add_argument('recipe',help='Recipe JSON path, or - to read stdin.')
        cmd.add_argument('--strict',action='store_true',help='Treat topology warnings as errors.')
        if name in ('build','preview'):
            cmd.add_argument('-o','--output',required=True,help='Dedicated generated-output directory.')
            if name == 'build': cmd.add_argument('--preview',action='store_true')
            cmd.add_argument('--compiler',type=Path,default=ROOT/'build'/'meic')
            cmd.add_argument('--runner',type=Path,default=ROOT/'build'/'mei-headless')
            cmd.add_argument('--verify',action='store_true',help='Block export on geometry or triangle-visibility failures; also enforced by recipe verification.required.')
            cmd.add_argument('--probe',type=Path,default=ROOT/'build'/'mei-asset-probe')
        elif name=='verify':
            cmd.add_argument('-o','--output',help='Save verification.json and triangle-ID difference images.')
            cmd.add_argument('--compiler',type=Path,default=ROOT/'build'/'meic')
            cmd.add_argument('--probe',type=Path,default=ROOT/'build'/'mei-asset-probe')
            cmd.add_argument('--yaw-steps',type=int)
            cmd.add_argument('--pitches',help='Comma-separated camera pitches in radians; use --pitches=-0.35,0,0.35.')
            cmd.add_argument('--distances',help='Comma-separated multipliers of the fitted camera distance.')
            cmd.add_argument('--far',type=float,help='Ordering-table far depth; default 100, matching Mei camera defaults.')
            cmd.add_argument('--geometry',choices=['error','warn'],help='Default error. warn explicitly permits geometric intersections while still enforcing visibility.')
            cmd.add_argument('--yaw-range',help='Two camera yaws in degrees, FROM,TO: sample only that arc (an asset seen from one side).')
            cmd.add_argument('--edge-margin',type=float,help='Pixels near a face outline left undecided (default 1, as the World Checker; 0: every pixel).')
            cmd.add_argument('--scale',choices=['fit','world'],help='fit (default): scaled to about 2 units; world: at its own size, sorting as in a world.')
            cmd.add_argument('--depth',action='store_true',help='Judge the asset as drawn with the depth buffer (policy depth: true).')
            cmd.add_argument('--perspective',action='store_true',help='Draw it with perspective-correct texturing (policy perspective: true).')
    imp = sub.add_parser('import-obj',help='Convert OBJ geometry into an editable recipe; materials/UVs are not imported.')
    imp.add_argument('input')
    imp.add_argument('-o','--output',required=True)
    imp.add_argument('--name',default='imported')
    imp.add_argument('--force',action='store_true')
    return p


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == 'schema':
            output(SCHEMA)
        elif args.command == 'init':
            recipe = load(str(EXAMPLES/(args.example+'.asset.json')))
            compile_recipe(recipe)
            write_new(args.output,recipe,args.force)
            output({'ok':True,'recipe':str(Path(args.output).resolve()),'next':'inspect, then preview this recipe'})
        elif args.command == 'import-obj':
            with Path(args.input).open() as stream: text = stream.read(MAX_INPUT+1)
            if len(text) > MAX_INPUT: raise AssetError('/input','Input exceeds 8 MiB.')
            recipe = import_obj(text,args.name)
            write_new(args.output,recipe,args.force)
            output({'ok':True,'recipe':str(Path(args.output).resolve()),
                    'warnings':['Geometry only: OBJ materials, UVs and supplied normals are not imported. Assign recipe materials before building.']})
        else:
            recipe = load(args.recipe)
            _,_,report = compile_recipe(recipe)
            if args.strict and report['warnings']:
                output(dict(report,ok=False,errors=[{'path':'/nodes','message':'Topology warnings rejected by --strict.'}]))
                return 1
            if args.command in ('build','preview'):
                report = build(recipe,args.output,args.command == 'preview' or args.preview,
                               args.compiler.resolve(),args.runner.resolve(),args.recipe,args.verify,args.probe.resolve())
            elif args.command=='verify':
                from assetkit.visibility import verify
                profile={}
                if args.yaw_steps is not None:profile['yaw_steps']=args.yaw_steps
                if args.geometry is not None:profile['geometry']=args.geometry
                if args.far is not None:profile['far']=args.far
                if args.scale is not None:profile['scale']=args.scale
                if args.edge_margin is not None:profile['edge_margin']=args.edge_margin
                if args.depth:profile['depth']=True
                if args.perspective:profile['perspective']=True
                if args.yaw_range is not None:profile['yaw_range_degrees']=[float(n) for n in args.yaw_range.split(',')]
                for key in ('pitches','distances'):
                    if getattr(args,key) is not None:profile[key]=[float(n) for n in getattr(args,key).split(',')]
                if args.output and args.recipe!='-' and (Path(args.output).resolve()/'verification.json')==Path(args.recipe).resolve():
                    raise AssetError('/output','Verification report would overwrite the source recipe.')
                report=verify(recipe,profile,args.output,args.compiler.resolve(),args.probe.resolve())
            output(report)
            if not report['ok']:return 1
        return 0
    except (AssetError,OSError,ValueError,RecursionError) as error:
        output({**getattr(error,'report',{}),'ok':False,'errors':[{'path':getattr(error,'path','/input'),'message':str(error)}]})
        return 1


if __name__ == '__main__':
    sys.exit(main())
