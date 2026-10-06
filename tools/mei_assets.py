#!/usr/bin/env python3
"""Mei Asset Kit: agent-first procedural 3D modeling and native render feedback.

Run `python3 tools/mei_assets.py schema` for the complete recipe contract, or
read docs/ASSETKIT.md. All command results and errors are JSON on stdout.
"""
import json
import os
from pathlib import Path
import re
import shutil
import sys

from kitcore import jsonio, output as staged
from kitcore.cli import parser_class
from assetkit.compiler import (AssetError, compile_recipe, native_bytes,
                               editor_project, obj_text, import_obj, import_source,
                               material_manifest, palette_bytes, texture_outputs, SWATCH)
from assetkit.preview import source, render, parse_camera, cameras_file
from assetkit import gltf
from assetkit.schema import SCHEMA

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT/'examples'/'assets'
MAX_INPUT = jsonio.MAX_INPUT
output = jsonio.output
write_new = jsonio.write_new


def load(path):
    return jsonio.load(path,AssetError)


def drawn_with(recipe, mesh, drawn=None):
    """(depth, perspective) a preview draws with: build/preview --depth and --perspective, else a
    textured asset's policy depth (with perspective). An untextured asset's policy alone does not
    change its preview, so the files of recipes made before depth mode stay the same."""
    if drawn:
        return drawn.get('depth',False),drawn.get('perspective',False) or None
    return bool(mesh.textures) and recipe.get('verification',{}).get('depth',False),None


def artifacts(recipe, mesh, materials, report, drawn=None):
    name = recipe['name']
    depth,perspective = drawn_with(recipe,mesh,drawn)
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
        'preview.akr':source(name,report['bounds'],load=bool(mesh.palette or mesh.textures),
                             depth=depth,perspective=perspective).encode(),
        'report.json':(json.dumps(report,indent=2)+'\n').encode(),
    }
    # Every build has a manifest; only palette-backed meshes have palettes and a swatch, so
    # the files legacy recipes always had are unchanged.
    files[name+'.materials.json'] = (json.dumps(material_manifest(mesh,materials,recipe),indent=2)+'\n').encode()
    if mesh.palette:
        files[name+'.pal'] = palette_bytes(mesh)
        files[name+'.swatch'] = SWATCH
    # Textured meshes: the texels of each slot used, the palettes and animation frames.
    if mesh.textures:
        files.update(texture_outputs(name,mesh)[0])
    # Levels of detail: a mesh each, embedded after level 0 (they share its palette entries).
    for k,(level,_) in enumerate(mesh.levels or [],1):
        files[f'{name}.lod{k}.bin'] = native_bytes(level,materials,recipe.get('lighting',{}))
        files[name+'.akr'] += f'embed ASSET_{name.upper()}_LOD{k}: Mesh = "{name}.lod{k}.bin"\n'.encode()
    return files


class VerificationFailure(AssetError):
    def __init__(self, report, renders=None):
        failures=report.get('failures',[])
        listed='; '.join(failures[:6])+(f'; and {len(failures)-6} more' if len(failures)>6 else '')
        where=(f' Failing preview renders (not exported): {renders}.' if renders else
               ' Run preview to see failing renders of the model.')
        super().__init__('/verification',f'Export blocked by verification: {listed or report.get("verdict","failed")}. '
                         f'The full report is verification.failed.json.{where}')
        self.report=report


TOOLS = (('compiler','MEIC','meic'),('runner','RUN','mei-headless'),('probe','PROBE','mei-asset-probe'))


def tool_paths(args, environ=None):
    """{tool: (path, where it came from)} for the native tools a command takes, each from the
    first of: its own option (--compiler, --runner, --probe), --build-dir DIR, its environment
    variable (MEIC, RUN, PROBE, as the test suites read them), $B (make's build directory,
    relative to the repository), build/."""
    environ = os.environ if environ is None else environ
    out = {}
    for key,variable,executable in TOOLS:
        if not hasattr(args,key): continue
        given,build_dir = getattr(args,key),getattr(args,'build_dir',None)
        if given is not None: path,how = given,f'--{key} {given}'
        elif build_dir is not None: path,how = Path(build_dir)/executable,f'--build-dir {build_dir}'
        elif environ.get(variable): path,how = Path(environ[variable]),f'{variable}={environ[variable]}'
        elif environ.get('B'): path,how = ROOT/environ['B']/executable,f'B={environ["B"]}'
        else: path,how = ROOT/'build'/executable,'the default, build/'
        out[key] = (path.resolve(),how)
    return out


def require_tools(tools, keys):
    """An error naming each missing tool, the directory looked in, how it was chosen, the make
    command that builds it and how to point the kit elsewhere."""
    missing = [(key,*tools[key]) for key in dict.fromkeys(keys) if not tools[key][0].is_file()]
    if not missing: return
    lines = []
    for key,path,how in missing:
        directory = path.parent
        try: shown = directory.relative_to(ROOT)
        except ValueError: shown = directory
        lines.append(f'Missing {path.name} in {directory} (the {key}, from {how}): build it with '
                     f'make B={shown} {shown}/{path.name}')
    raise AssetError('/arguments/tools','. '.join(lines)+'. To use another build directory, pass --build-dir DIR '
                     '(the directory make B=DIR builds into) or set B=DIR, or MEIC, RUN and PROBE for single tools, '
                     'or --compiler, --runner and --probe.')


SINK = 0.02          # how far flush_contacts suggests sinking a part into its neighbour (units)
BOX_SIDE_OF = {(0,1):'right',(0,-1):'left',(1,1):'top',(1,-1):'bottom',(2,1):'front',(2,-1):'back'}


def direction(n):
    """'-Y' for an axis-aligned unit normal, else the vector rounded."""
    k = max(range(3),key=lambda i: abs(n[i]))
    if abs(abs(n[k])-1) < 1e-6: return ('+' if n[k] > 0 else '-')+'XYZ'[k]
    return '['+', '.join(f'{x:.2f}' for x in n)+']'


def contact_fixes(mesh, findings, depth=True):
    """One line per part pair of flush findings: which part to move, where and by about how much.
    The smaller part (by surface area) is the one to move."""
    from assetkit.geometry import cross, sub, dot, norm
    area = {}
    for f in mesh.faces:
        a,b,c = (mesh.vertices[i] for i in f.indices)
        n = cross(sub(b,a),sub(c,a))
        area[f.part] = area.get(f.part,0)+dot(n,n)**.5/2
    first, count = {}, {}
    for f in findings:
        pair = tuple(sorted((f['a']['part'],f['b']['part'])))
        first.setdefault(pair,f)
        count[pair] = count.get(pair,0)+1
    lines = []
    # in the order of the audit's summary: the largest first
    for (p,q),f in sorted(first.items(),key=lambda kv:(-count[kv[0]],kv[0])):
        if f['code'] == 'duplicate_face':
            lines.append(f'{p} and {q}: remove one of the coincident faces (faces {f["a"]["face"]}/{f["b"]["face"]}); '
                         'a mirror or array copy laid over the original makes them')
            continue
        if p == q:
            lines.append(f'within {p}: two of its faces lie flush in one plane (faces {f["a"]["face"]}/{f["b"]["face"]}); '
                         'remove the covered one or split the part (a mirror copy over the original?)')
            continue
        faces = {f['a']['part']:f['a']['face'],f['b']['part']:f['b']['face']}
        small,big = (p,q) if area.get(p,0) <= area.get(q,0) else (q,p)
        normal = lambda part: norm(cross(*(sub(mesh.vertices[mesh.faces[faces[part]].indices[k]],
                                                mesh.vertices[mesh.faces[faces[part]].indices[0]]) for k in (1,2))))
        ns = normal(small)
        toward = direction(ns)
        k = max(range(3),key=lambda i: abs(ns[i]))
        side = BOX_SIDE_OF.get((k,1 if ns[k] > 0 else -1)) if len(toward) == 2 else None
        opened = f'open {small}\'s face toward {toward}' + (f' (an unrotated box: "open": ["{side}"])' if side else '')
        if dot(ns,normal(big)) < 0:
            # back to back: one part stands on or against the other
            sink = f'sink {small} about {SINK} along {toward} into {big}, or {opened}'
            lines.append(sink if depth else f'{opened}; sinking {small} into {big} would make them cross, '
                         'which fails without the depth buffer')
        else:
            lines.append(f'move {small} about 0.03 along {toward} so its face stands proud of {big}\'s '
                         '(closer than 3 cm z-fights from a distance), or remove the covered face')
    return lines


def flush_contacts(mesh, depth=True):
    """The check for flush faces before rendering (inspect, and build and preview): duplicate
    faces and coplanar overlaps, which the Asset Checker fails in either mode, by part pair,
    with a fix per pair. Needs NumPy; without it, says so."""
    from assetkit.geometry_audit import geometry_audit
    try:
        audit = geometry_audit(mesh,crossings=False)
    except AssetError as error:
        return {'checked':False,'message':str(error)}
    result = {'checked':True,'count':len(audit['findings']),'by_code':audit['failing'],'summary':audit['summary']}
    if audit['findings']:
        result['hint'] = ('Faces of two parts lie flush in one plane: the Asset Checker fails these in either mode. '
                          'Sink one part 1-2 cm into its neighbour, or open the hidden face (a box\'s open sides).')
        result['fixes'] = contact_fixes(mesh,audit['findings'],depth)
    return result


class FlushContacts(AssetError):
    """build and preview stop before rendering when the recipe requires the Asset Checker and the
    mesh has flush contacts, which it would fail."""
    def __init__(self, flush):
        listed = '; '.join(flush['summary'][:6])+(f'; and {len(flush["summary"])-6} more' if len(flush['summary']) > 6 else '')
        fixes = '; '.join(flush['fixes'][:6])
        super().__init__('/verification',f'Stopped before rendering: {flush["count"]} flush contacts, which the Asset Checker '
                         f'fails in either mode: {listed}. Fix: {fixes}. Nothing was written; run inspect to see them all.')
        self.report = {'flush_contacts':flush}


def close_contacts(mesh):
    """inspect's and verify's warning of faces facing the same way closer than 3 cm (geometry_audit.close_faces)."""
    from assetkit.geometry_audit import close_faces
    try:
        return {'checked':True,**close_faces(mesh)}
    except AssetError as error:
        return {'checked':False,'message':str(error)}


def camera_views(shots, report):
    """The world-scale views a build renders: --closeups, then --part, --cameras and --camera."""
    from assetkit.preview import closeups, part_camera
    if not shots: return []
    views=closeups(report['bounds']) if shots.get('closeups') else []
    views+=[part_camera(report['parts'],part,report.get('decals',())) for part in shots.get('parts',[])]
    views+=list(shots.get('cameras',[]))
    names=[v['name'] for v in views]
    if len(set(names))!=len(names):
        raise AssetError('/arguments/camera',f'Camera names must differ: {", ".join(sorted({n for n in names if names.count(n)>1}))}.')
    return views


def previews(directory, recipe, mesh, report, compiler, runner, drawn, shots, views, failing=False):
    """The six fitted views and contact sheet, and the world-scale camera views (camera_views()),
    rendered in directory (which holds the built asset)."""
    from assetkit.preview import render_cameras
    load=bool(mesh.palette or mesh.textures)
    depth,perspective=drawn_with(recipe,mesh,drawn)
    result=render(directory,recipe['name'],report['bounds'],compiler,runner,load,depth,perspective,failing)
    if views:
        # camera views draw as a game does and the Asset Checker judges: with the depth buffer
        # also when only the recipe's policy says so (the six views keep their earlier files)
        policy=recipe.get('verification',{})
        result['cameras']=render_cameras(directory,recipe['name'],report['bounds'],views,compiler,runner,load,
                                         depth or policy.get('depth',False),
                                         perspective or policy.get('perspective',False) or None,
                                         (shots or {}).get('upscale',2),failing)
    return result


def preview_files(directory):
    return [p for pattern in ('view_*.png','camera_*.png','contact.png','cameras.png') for p in sorted(Path(directory).glob(pattern))]


def folder(input_path):
    """The folder a recipe's image paths are relative to: its own (the current one for stdin)."""
    return Path(input_path).resolve().parent if input_path and input_path != '-' else None


def build(recipe, directory, preview=False, compiler=None, runner=None, input_path=None, verification=False, probe=None,
          drawn=None, shots=None, flush_check=False):
    """flush_check (the CLI's build and preview): check for flush contacts first (flush_contacts),
    put them in the report, and stop before rendering or writing anything when the Asset Checker
    is to run and would fail them.
    drawn: {'depth': True, 'perspective': True} or part of it (build/preview --depth and
    --perspective): the asset is drawn so, as in a world whose runtime says so. Its preview draws
    so, and the Asset Checker judges it so (where the recipe's policy does not set them).
    shots: the preview's world-scale views, {'cameras': [camera()...], 'parts': [ids],
    'closeups': bool, 'upscale': n}. When verification fails and a preview was asked for, the
    previews are still rendered, marked as failing, into verification-failed/preview/."""
    mesh,materials,report = compile_recipe(recipe,folder(input_path))
    views = camera_views(shots,report) if preview else []     # named parts checked before any work
    if flush_check:
        policy = recipe.get('verification')
        checking = verification or (policy is not None and policy.get('required',True))
        depth = (policy or {}).get('depth',bool((drawn or {}).get('depth')))
        flush = flush_contacts(mesh,depth)
        for k,(level,_) in enumerate((mesh.levels or []) if flush['checked'] else [],1):
            more = flush_contacts(level,depth)
            if more.get('count'):
                flush['count'] += more['count']
                for code,n in more['by_code'].items(): flush['by_code'][code] = flush['by_code'].get(code,0)+n
                flush['summary'] += [f'lod {k} {line}' for line in more['summary']]
                flush['fixes'] = flush.get('fixes',[])+[f'lod {k} {line}' for line in more['fixes']]
                flush.setdefault('hint',more['hint'])
        if checking and (policy or {}).get('geometry','error') != 'warn' and flush.get('count'):
            raise FlushContacts(flush)
        report['flush_contacts'] = flush
    files = artifacts(recipe,mesh,materials,report,drawn)
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
            policy=recipe.get('verification',{})
            profile={k:True for k in ('depth','perspective') if (drawn or {}).get(k) and k not in policy}
            checked=verify(recipe,profile or None,directory=stage,compiler=compiler,probe=probe,folder=folder(input_path))
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
                renders=None
                if preview:
                    # the model as it stands, so that it can be seen while being repaired
                    renders_dir=directory/'verification-failed'/'preview'
                    shutil.rmtree(renders_dir,ignore_errors=True)
                    try:
                        shown=previews(stage,recipe,mesh,report,compiler,runner,drawn,shots,views,failing=True)
                    except AssetError as error:
                        checked['preview']={'error':str(error)}
                    else:
                        renders_dir.mkdir(parents=True)
                        for path in preview_files(stage):path.replace(renders_dir/path.name)
                        shown['contact']=str(renders_dir/'contact.png')
                        if 'cameras' in shown:shown['cameras']['contact']=str(renders_dir/'cameras.png')
                        shown['directory']=str(renders_dir)
                        checked['preview']=shown
                        renders=shown['contact']+(' and '+shown['cameras']['contact'] if 'cameras' in shown else '')
                failure.write_text(json.dumps(checked,indent=2)+'\n')
                raise VerificationFailure(checked,renders)
            report['verification']=checked
        if preview:
            report['preview'] = previews(stage,recipe,mesh,report,compiler,runner,drawn,shots,views)
            report['preview']['contact'] = str(directory/'contact.png')
            if 'cameras' in report['preview']:
                report['preview']['cameras']['contact'] = str(directory/'cameras.png')
        (stage/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        generated = sorted(p.name for p in stage.iterdir())
        if input_path and input_path != '-' and any(directory/name == Path(input_path).resolve() for name in generated):
            raise AssetError('/output','Generated preview would overwrite the source recipe. Use a separate output directory.')
        staged.commit(stage,directory)
    report['output'] = str(directory)
    report['files'] = generated
    return report


def images_of(recipe):
    """The files a recipe's textures read, relative to its folder: images, sheets and the
    sheets' NAME.sheet.json."""
    names = [m['texture']['image'] for m in recipe.get('materials',{}).values() if 'image' in m.get('texture',{})]
    for sheet in recipe.get('sheets',{}).values():
        names.append(sheet['image'])
        if 'grid' not in sheet:
            names.append(str(Path(sheet['image']).with_suffix('.sheet.json')))
    return sorted(set(names))


def slot_list(text):
    """'14-10' -> [14, 13, 12, 11, 10]; '14,12' -> [14, 12]."""
    try:
        if '-' in text:
            a,b = (int(n) for n in text.split('-'))
            slots = list(range(a,b-1,-1)) if a >= b else list(range(a,b+1))
        else:
            slots = [int(n) for n in text.split(',')]
    except ValueError as error:
        raise AssetError('/arguments/slots','Give slots as a range (14-10) or a list (14,12).') from error
    if not slots or any(not 0 <= s <= 14 for s in slots) or len(set(slots)) != len(slots):
        raise AssetError('/arguments/slots','Slots are 0-14, each once (15 holds the fonts).')
    return slots


def pack_command(args):
    from assetkit.packer import pack
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}',args.name):
        raise AssetError('/arguments/name','A pack name uses lowercase letters, digits and underscores, beginning with a letter.')
    if not 0 <= args.palette <= 254 or not 0 <= args.palette8 <= 14:
        raise AssetError('/arguments/palette','--palette is 0-254 and --palette8 0-14 (palette 255 and 8-bit palette 15 hold the fonts).')
    recipes = [(load(path),folder(path)) for path in args.recipes]
    files,manifest = pack(recipes,args.name,slot_list(args.slots),args.palette,args.palette8,args.swatch)
    directory = Path(args.output).resolve()
    staged.guard(directory,files,args.recipes,error=AssetError)
    with staged.staging(directory,'.mei-assets-') as stage:
        for filename,data in files.items(): (stage/filename).write_bytes(data)
        names = staged.commit(stage,directory)
    return {'ok':True,'output':str(directory),'files':names,**{k:v for k,v in manifest.items() if k != 'assets'},
            'assets':[{k:a[k] for k in ('name','mesh','vertices','triangles')} for a in manifest['assets']]}


ArgumentParser = parser_class(AssetError)


def parser():
    p = ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('schema',help='Print the complete JSON Schema; no file access needed.')
    init = sub.add_parser('init',help='Write an editable example recipe (never overwrite by default).')
    init.add_argument('output')
    init.add_argument('--example',choices=['robot','vessel','cottage','kiosk','stall'],default='robot')
    init.add_argument('--force',action='store_true')
    for name in ('validate','inspect','build','preview','verify'):
        cmd = sub.add_parser(name,help={'validate':'Validate schema, topology and Mei budgets.',
                                      'inspect':'Return bounds, costs and diagnostics per named part.',
                                      'build':'Export native meshes, Akari import, OBJ and editor project.',
                                      'preview':'Build and render six views using the actual Mei GPU.',
                                      'verify':'Audit geometry and native triangle visibility across a camera sweep.'}[name])
        cmd.add_argument('recipe',help='Recipe JSON path, or - to read stdin.')
        cmd.add_argument('--strict',action='store_true',help='Treat topology warnings as errors.')
        if name in ('build','preview','verify'):
            cmd.add_argument('--build-dir',type=Path,help='The Mei build directory with meic, mei-headless and mei-asset-probe '
                             '(make B=DIR). Default: $MEIC, $RUN and $PROBE for each tool, else $B, else build/.')
            cmd.add_argument('--compiler',type=Path,help='meic to use (overrides --build-dir).')
            cmd.add_argument('--probe',type=Path,help='mei-asset-probe to use (overrides --build-dir).')
        if name in ('build','preview'):
            cmd.add_argument('-o','--output',required=True,help='Dedicated generated-output directory.')
            if name == 'build': cmd.add_argument('--preview',action='store_true')
            cmd.add_argument('--runner',type=Path,help='mei-headless to use (overrides --build-dir).')
            cmd.add_argument('--verify',action='store_true',help='Block export on geometry or triangle-visibility failures; also enforced by recipe verification.required.')
            cmd.add_argument('--camera',action='append',default=[],metavar='SPEC',
                             help='A world-scale view: NAME=EX,EY,EZ:TX,TY,TZ (eye and target) or NAME=EX,EY,EZ@YAW,PITCH '
                                  '(degrees; yaw 0 looks along +Z, positive toward +X; positive pitch looks up). Repeatable.')
            cmd.add_argument('--cameras',type=Path,metavar='FILE',
                             help='A JSON list of views: {"name", "eye", "target"} or {"name", "eye", "yaw", "pitch"}.')
            cmd.add_argument('--part',action='append',default=[],metavar='ID',help='A world-scale view framing this part (an id in inspect\'s parts). Repeatable.')
            cmd.add_argument('--closeups',action='store_true',help='Automatic world-scale views: eye_level, and close-ups along a long asset.')
            cmd.add_argument('--upscale',type=int,default=2,choices=[1,2,3,4],help='Whole-number scale of the camera views\' images (default 2: 640 x 480).')
            cmd.add_argument('--depth',action='store_true',help='The asset is drawn with the depth buffer, as in a world whose runtime says so: preview so, and verify in depth mode where the recipe\'s policy does not set depth.')
            cmd.add_argument('--perspective',action='store_true',help='The asset is drawn with perspective-correct texturing (preview so; policy perspective where the recipe does not set it).')
        elif name=='verify':
            cmd.add_argument('-o','--output',help='Save verification.json and triangle-ID difference images.')
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
            cmd.add_argument('--depth-views',type=int,help='With depth: the views of the sweep judged (default 16; more if needed to judge every face drawn).')
    pk = sub.add_parser('pack',help='Pack several assets (or one) for a cart without a world: shared texture slots and palettes, one loader.')
    pk.add_argument('recipes',nargs='+',help='Recipe JSON paths.')
    pk.add_argument('-o','--output',required=True,help='Dedicated generated-output directory.')
    pk.add_argument('--name',default='assets',help='Name of the Akari file, its loader NAME_load() and the data files (default assets).')
    pk.add_argument('--slots',default='14-0',help='Texture slots to use, in order: a range 14-10 or a list 14,12 (never 15). Default 14-0.')
    pk.add_argument('--palette',type=int,default=0,help='First 4-bit palette (palette-backed materials, then 4-bit textures). Default 0.')
    pk.add_argument('--palette8',type=int,default=14,help='First 8-bit palette for 8-bit textures (they take it and those below). Default 14.')
    pk.add_argument('--swatch',action='store_true',help='Keep the swatch block (row 0 of the first slot) and load the swatch even with no palette-backed material: the textures can then share a slot with a world\'s swatch.')
    gltf.add_parser(sub)
    imp = sub.add_parser('import-obj',help='Convert OBJ geometry into an editable recipe; materials/UVs are not imported.')
    imp.add_argument('input')
    imp.add_argument('-o','--output',required=True)
    imp.add_argument('--name',default='imported')
    imp.add_argument('--force',action='store_true')
    return p


def node_of(recipe, path):
    """The ids of the nodes a JSON Pointer path runs through, as inspect's parts name them (a node
    without an id is OP_INDEX): '/nodes/2/children/0/size' -> 'body/arm'. Prototypes and levels of
    detail say so: 'prototype wheel: rim', 'lod level 1: body'. None outside the nodes."""
    if not isinstance(recipe, dict) or not isinstance(path, str) or not path.startswith('/'): return None
    tokens, value, names, context = path[1:].split('/'), recipe, [], ''
    for k,token in enumerate(tokens):
        if isinstance(value, list):
            if not token.isdigit() or int(token) >= len(value): break
            value = value[int(token)]
            if k and tokens[k-1] in ('nodes','children') and isinstance(value, dict) and 'op' in value:
                names.append(value.get('id', f'{value["op"]}_{token}'))
        elif isinstance(value, dict):
            if token not in value: break
            value = value[token]
            if k and tokens[k-1] == 'prototypes' and isinstance(value, dict) and 'op' in value:
                context = f'prototype {token}: '
                if 'id' in value: names.append(value['id'])
            if k > 1 and tokens[k-2] == 'levels' and token == 'nodes':
                context = f'lod level {int(tokens[k-1])+1}: '
        else:
            break
    return context+'/'.join(names) if names else None


def inspect_extras(recipe, mesh, report):
    """What inspect adds to the compile report: flush contacts (with a fix per part pair), close
    parallel faces, the repeating texture windows in use, and warnings for mirror copies over
    their originals and for parts below y = 0."""
    policy = recipe.get('verification')
    depth = policy.get('depth',False) if policy is not None else True
    report['flush_contacts'] = flush_contacts(mesh,depth)
    report['close_faces'] = close_contacts(mesh)
    if mesh.textures:
        from assetkit.compiler import window_order
        from assetkit.textures import describe, MAX_WINDOWS
        packing, textures = mesh.textures['packing'], mesh.textures['textures']
        windows = []
        for k,key in enumerate(window_order(mesh,packing),1):
            users = [t for t in textures.values() if t.tile.key == key]
            windows.append({'window':k,'texture':describe(users[0]),'size':[users[0].width,users[0].height],
                            'bits':users[0].bits,'materials':sorted(t.material for t in users)})
        report['texture_windows'] = {'used':len(windows),'max':MAX_WINDOWS,'windows':windows}
    report['warnings'] += mesh.notes or []
    below = [(part['bounds']['min'][1],part['id']) for part in report['parts'] if part['bounds']['min'][1] < 0]
    if below:
        report['warnings'].append({'code':'below_ground','parts':[name for _,name in sorted(below)],'min_y':min(below)[0],
                                   'message':f'{len(below)} part{"s reach" if len(below) > 1 else " reaches"} below y = 0, the ground '
                                             f'the asset stands on (lowest {min(below)[1]}, at y = {min(below)[0]:.4g}): '
                                             'intentional if sunk into the ground or hanging from a mount; otherwise raise them.'})


def main(argv=None):
    recipe = None
    try:
        args = parser().parse_args(argv)
        if args.command == 'schema':
            output(SCHEMA)
        elif args.command == 'init':
            recipe = load(str(EXAMPLES/(args.example+'.asset.json')))
            compile_recipe(recipe,EXAMPLES)
            write_new(args.output,recipe,args.force)
            # an example with images: copy them beside the new recipe, at the same relative paths
            for name in images_of(recipe):
                target = Path(args.output).resolve().parent/name
                if args.force or not target.exists():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes((EXAMPLES/name).read_bytes())
            output({'ok':True,'recipe':str(Path(args.output).resolve()),'next':'inspect, then preview this recipe'})
        elif args.command == 'pack':
            output(pack_command(args))
        elif args.command == 'export':
            output(gltf.command(args,load,folder))
        elif args.command == 'import-obj':
            with Path(args.input).open() as stream: text = stream.read(MAX_INPUT+1)
            if len(text) > MAX_INPUT: raise AssetError('/input','Input exceeds 8 MiB.')
            recipe = import_obj(text,args.name)
            write_new(args.output,recipe,args.force)
            output({'ok':True,'recipe':str(Path(args.output).resolve()),
                    'warnings':['Geometry only: OBJ materials, UVs and supplied normals are not imported. Assign recipe materials before building.']})
        else:
            recipe = load(args.recipe)
            # inspect reports a recipe over its budgets in full, the breach a warning
            mesh,_,report = compile_recipe(recipe,folder(args.recipe),'warn' if args.command == 'inspect' else 'error')
            if args.strict and report['warnings']:
                output(dict(report,ok=False,errors=[{'path':'/nodes','message':'Topology warnings rejected by --strict.'}]))
                return 1
            if args.command == 'inspect':
                inspect_extras(recipe,mesh,report)
            tools = tool_paths(args)
            if args.command in ('build','preview'):
                drawn = {k:True for k in ('depth','perspective') if getattr(args,k)}
                preview = args.command == 'preview' or args.preview
                policy = recipe.get('verification')
                checking = args.verify or (policy is not None and policy.get('required',True))
                require_tools(tools,(['compiler','runner'] if preview else [])+(['compiler','probe'] if checking else []))
                shots = {'cameras':[parse_camera(text,k) for k,text in enumerate(args.camera)],'parts':args.part,
                         'closeups':args.closeups,'upscale':args.upscale}
                if args.cameras:
                    shots['cameras'] = cameras_file(load(str(args.cameras)))+shots['cameras']
                report = build(recipe,args.output,preview,tools['compiler'][0],tools['runner'][0],args.recipe,args.verify,
                               tools['probe'][0],drawn,shots,flush_check=True)
            elif args.command=='verify':
                require_tools(tools,['compiler','probe'])
                from assetkit.visibility import verify
                profile={}
                if args.yaw_steps is not None:profile['yaw_steps']=args.yaw_steps
                if args.geometry is not None:profile['geometry']=args.geometry
                if args.far is not None:profile['far']=args.far
                if args.scale is not None:profile['scale']=args.scale
                if args.edge_margin is not None:profile['edge_margin']=args.edge_margin
                if args.depth_views is not None:profile['depth_views']=args.depth_views
                if args.depth:profile['depth']=True
                if args.perspective:profile['perspective']=True
                if args.yaw_range is not None:profile['yaw_range_degrees']=[float(n) for n in args.yaw_range.split(',')]
                for key in ('pitches','distances'):
                    if getattr(args,key) is not None:profile[key]=[float(n) for n in getattr(args,key).split(',')]
                if args.output and args.recipe!='-' and (Path(args.output).resolve()/'verification.json')==Path(args.recipe).resolve():
                    raise AssetError('/output','Verification report would overwrite the source recipe.')
                report=verify(recipe,profile,args.output,tools['compiler'][0],tools['probe'][0],folder(args.recipe))
            output(report)
            if not report['ok']:return 1
        return 0
    except (AssetError,OSError,ValueError,RecursionError) as error:
        # the errors first, so that the reason leads a long failure report
        path = getattr(error,'path','/input')
        node = node_of(recipe,path)
        output({'ok':False,'errors':[{'path':path,**({'node':node} if node else {}),'message':str(error)}],
                **{k:v for k,v in getattr(error,'report',{}).items() if k not in ('ok','errors')}})
        return 1


if __name__ == '__main__':
    sys.exit(main())
