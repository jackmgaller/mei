#!/usr/bin/env python3
"""Mei World Kit: agent-first world recipes (cells, regions, layers, game data) to world packs.

Run `python3 tools/mei_world.py schema` for the complete recipe contract (the game schema's
Mochi form is described under $defs/game x-mochi), or read docs/WORLDKIT.md. All command results
and errors are JSON on stdout; exit 0 or 1. The quick tools (check, floors, textures, cracks) print
plain text, or JSON with --json.
"""
import os
from pathlib import Path
import shutil
import sys

from kitcore import jsonio
from kitcore.cli import parser_class
from assetkit.geometry import AssetError
from worldkit.schema import WorldError, published
from worldkit.build import build, compile_source
from worldkit.world import load_game
from worldkit import mochi

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT/'examples'/'worlds'
EXAMPLE_WORLDS = {'room':'test_room','city':'two_districts','terrain':'shrine_grounds'}


def summary(report, cell=None):
    """inspect's result: the report, optionally narrowed to one cell."""
    if cell is None: return report
    cells = [c for c in report['cells'] if c['id'] == cell]
    if not cells: raise WorldError('/arguments',f'No cell {cell!r}.')
    return dict(report,cells=cells,regions={cells[0]['region']:report['regions'][cells[0]['region']]})


def init(directory, example, force=False):
    target = Path(directory)
    if target.exists() and any(target.iterdir()) and not force:
        raise WorldError('/arguments',f'{target} is not empty. Choose a new directory, or pass --force.')
    source = EXAMPLES/EXAMPLE_WORLDS[example]
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.ids.json'))
    world = target/f'{EXAMPLE_WORLDS[example]}.world.json'
    compile_source(str(world))
    return {'ok':True,'world':str(world.resolve()),'next':'inspect, then build this world'}


def convert(source, output=None, force=False):
    """A game schema in the other form: JSON to canonical Mochi, Mochi (.mochi) to JSON."""
    game = load_game(source)
    to = 'json' if source.endswith('.mochi') else 'mochi'
    text = jsonio.pretty(game) if to == 'json' else mochi.format(game)
    if output is None:
        return {'ok':True,'format':to,'game':game} if to == 'json' else {'ok':True,'format':to,'text':text}
    target = Path(output)
    if target.suffix != '.'+to:
        raise WorldError('/arguments',f'This converts to {"JSON" if to == "json" else "Mochi"}: name the output *.{to}.')
    if target.exists() and not force:
        raise WorldError('/arguments',f'{target} exists. Choose a new path, or pass --force.')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text)
    return {'ok':True,'format':to,'output':str(target.resolve())}


def floors(recipe, points, assets=None):
    """The highest floor under each point (x, z), from the world's collision as the kit builds it
    (terrain, sweeps and placements), for putting things on the ground."""
    import math
    from worldkit import pack as P
    from worldkit.terrain import TAG_FIELD, TAG_SWEEP
    if len(points) % 2:
        raise WorldError('/arguments','Give points as X Z pairs.')
    source,compiled = compile_source(recipe,assets)
    fc = math.cos(math.radians(compiled.world.floor_max_degrees))
    names = {}
    for cs in source.cells:
        for k,pl in enumerate(cs.recipe.get('placements',[])): names[(tuple(cs.recipe['at']),k)] = pl['id']
    tris = []
    for cell in compiled.world.cells:
        for t in cell.collision:
            v = [tuple(float(c) for c in p) for p in (t.a,t.b,t.c)]
            n = P.front_normal(*v)
            ln = math.sqrt(P.dot3(n,n))
            if ln and n[1]/ln >= fc: tris.append((v,n,t,(cell.i,cell.j)))
    out = []
    for k in range(0,len(points),2):
        x,z = float(points[k]),float(points[k+1])
        best = None
        for v,n,t,cell in tris:
            sides = [(v[(e+1)%3][0]-v[e][0])*(z-v[e][2])-(v[(e+1)%3][2]-v[e][2])*(x-v[e][0]) for e in range(3)]
            if not (all(s >= -1e-9 for s in sides) or all(s <= 1e-9 for s in sides)): continue
            y = v[0][1]-(n[0]*(x-v[0][0])+n[2]*(z-v[0][2]))/n[1]
            if best is None or y > best[0]:
                what = ('terrain' if t.tag == TAG_FIELD else 'sweep' if t.tag == TAG_SWEEP else
                        names.get((cell,t.tag),'placement'))
                best = (y,what)
        out.append({'at':[x,z],'y':round(best[0],4) if best else None,'from':best[1] if best else None})
    return {'ok':True,'floors':out}


def build_dir(args):
    """The build directory the quick tools take their native tools and cache from: --build-dir,
    else $B (relative to the repository), else build/."""
    if args.build_dir is not None: return Path(args.build_dir).resolve()
    if os.environ.get('B'): return (ROOT/os.environ['B']).resolve()
    return ROOT/'build'


def quick_world(args):
    from worldkit.quick import load_world
    cache = None if args.no_cache else (args.cache or build_dir(args)/'kit-cache')
    return load_world(args.recipe,args.assets,cache,args.refresh)


def numbers(text, n, what):
    try:
        values = [float(v) for v in text.split(',')]
    except ValueError:
        values = []
    if len(values) != n:
        raise WorldError(f'/arguments/{what}',f'Give {what} as {n} numbers separated by commas, not {text!r}.')
    return values


def quick(args):
    """check, floors, textures and cracks: (result, its plain text)."""
    from worldkit import quick as Q
    world = quick_world(args)
    if args.command == 'check':
        cells = Q.parse_cells(args.cells,world)
        cameras = Q.parse_cameras(args.camera,args.cameras)
        if not cells and not cameras:
            raise WorldError('/arguments','Give --cells, --camera or --cameras: what to check.')
        b = build_dir(args)
        tools = {'compiler':(args.compiler or b/'meic').resolve(),
                 'probe':(args.probe or b/'mei-scene-probe').resolve()}
        for key,path in tools.items():
            if not path.is_file():
                raise WorldError('/arguments/tools',f'Missing {path} (the {key}): make B={os.path.relpath(path.parent,ROOT)} '
                                 f'{os.path.relpath(path,ROOT)}, or pass --build-dir.')
        report = Q.check(world,cells,cameras,tools,args.max_views,args.output)
        report['compiled'] = world.how()
        return report,Q.check_text(report,world,cells,cameras,args.rows)
    if args.command == 'cracks':
        from worldkit.build import cracks_path, load_crack_baseline
        from worldkit.world import load
        from kitcore import jsonio as J
        routes = Q.load_routes(args.routes) if args.routes else None
        source = load(args.recipe)
        path = Path(args.baseline) if args.baseline else cracks_path(source)
        baseline = None
        if args.baseline is not None and not args.write_baseline:
            _,baseline = load_crack_baseline(source,str(path))
        result = Q.cracks(world,routes,args.near,baseline)
        if args.write_baseline:
            path.write_text(J.pretty(Q.baseline_file(world,result['cracks'])))
            result['baseline_written'] = str(path)
        text = Q.cracks_text(result)
        if args.write_baseline: text += f'\nwrote {path}'
        return result,text
    if args.command == 'floors':
        result = Q.floors(world,numbers(args.area,4,'area'),args.step,
                          [l for l in args.layers.split(',') if l] if args.layers is not None else None,args.below)
        return result,Q.floors_text(result)
    cells = Q.parse_cells(args.cells,world)
    add, library = {}, None
    for spec in args.add:
        region,_,names = spec.partition(':')
        if not names:
            raise WorldError('/arguments/add','--add is REGION:ASSET[,ASSET...].')
        add.setdefault(region,[]).extend(n for n in names.split(',') if n)
    if add:
        from worldkit.assets import Library, asset_directories
        from worldkit.world import load
        source = load(args.recipe)
        dirs = asset_directories(source.world,source.base,args.assets)
        for region,names in add.items():
            # a recipe path (NAME.asset.json) is looked for in its own folder too
            for k,n in enumerate(names):
                if n.endswith('.asset.json'):
                    folder = Path(n).resolve().parent
                    if folder not in dirs: dirs.append(folder)
                    names[k] = Path(n).name[:-len('.asset.json')]
        library = Library(dirs[0],source.base,dirs[1:])
        for region in add:
            if region not in world.meta['regions']:
                raise WorldError('/arguments/add',f'No region {region!r}. Regions: {", ".join(world.meta["regions"])}.')
    result = Q.textures(world,args.region,cells,add,library)
    return result,Q.textures_text(result)


ArgumentParser = parser_class(WorldError)


def parser():
    p = ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    s = sub.add_parser('schema',help='Print the JSON Schema of world recipes, cell files and game schemas.')
    s.add_argument('--game',help='Fold this game schema\'s (Mochi or JSON) entity types and parameters in.')
    c = sub.add_parser('convert',help='Convert a game schema: JSON to canonical Mochi, or Mochi (.mochi) to JSON.')
    c.add_argument('game',help='Game schema path (- reads JSON from stdin).')
    c.add_argument('-o','--output',help='Write this file (*.mochi or *.json) instead of returning the result.')
    c.add_argument('--force',action='store_true',help='Overwrite the output file.')
    i = sub.add_parser('init',help='Copy an example world (world file, cells, game schema, asset recipes) into a directory.')
    i.add_argument('output')
    i.add_argument('--example',choices=sorted(EXAMPLE_WORLDS),default='room')
    i.add_argument('--force',action='store_true')
    f = sub.add_parser('floor',help='The highest floor under points (X Z pairs): terrain, a sweep or a placement\'s collision.')
    f.add_argument('recipe',help='World recipe path.')
    f.add_argument('points',nargs='+',help='X Z X Z ...: world coordinates seen from above.')
    f.add_argument('--assets',type=Path,help='Use this asset directory instead of the recipe\'s.')
    q = {}
    q['check'] = sub.add_parser('check',help='The World Checker on a few cells\' sampled views and collision, and on cameras, '
                                'with the world\'s thresholds: seconds, from a cached compile.')
    q['floors'] = sub.add_parser('floors',help='The pack\'s floor heights over an area as wp_floor() finds them, '
                                 'with what each belongs to, holes and cracks.')
    q['textures'] = sub.add_parser('textures',help='Texture VRAM per region, by asset and by image, against the budget.')
    q['cracks'] = sub.add_parser('cracks',help='Every collision crack the game\'s floor query does not bridge, on routes '
                                 'first, the widest first; compared with or written to the crack baseline.')
    for name,cmd in q.items():
        cmd.add_argument('recipe',help='World recipe path.')
        cmd.add_argument('--assets',type=Path,help='Use this asset directory instead of the recipe\'s.')
        cmd.add_argument('--json',action='store_true',help='The result as JSON (default: plain text).')
        cmd.add_argument('--build-dir',type=Path,help='The build directory (make B=DIR): native tools and the cache '
                         '(DIR/kit-cache). Default: $B, else build/.')
        cmd.add_argument('--cache',type=Path,help='Keep the compiled world here (default BUILD_DIR/kit-cache).')
        cmd.add_argument('--no-cache',action='store_true',help='Compile the world now and keep nothing.')
        cmd.add_argument('--refresh',action='store_true',help='Compile the world again even if nothing changed.')
    c = q['check']
    c.add_argument('--cells',action='append',default=[],metavar='I,J[;I,J...]',
                   help='Cells by their "at" (I,J) or ID, separated by ";" or the option repeated: their sampled views '
                        'and their static collision checks.')
    c.add_argument('--camera',action='append',default=[],metavar='SPEC',
                   help='A camera: NAME=EX,EY,EZ:TX,TY,TZ (eye and target) or NAME=EX,EY,EZ@YAW,PITCH (degrees; yaw 0 '
                        'looks along +Z, positive toward +X; positive pitch looks up). Repeatable.')
    c.add_argument('--cameras',action='append',type=Path,metavar='FILE',
                   help='A JSON list of cameras: {"name", "eye", "target"} or {"name", "eye", "yaw", "pitch"}.')
    c.add_argument('--max-views',type=int,default=200,help='At most this many sampled views (default 200; the '
                   'cameras always run).')
    c.add_argument('--rows',type=int,default=12,help='Sampled views listed, the worst first (default 12).')
    c.add_argument('-o','--output',type=Path,help='Also write world-check.json and pictures of the worst views here.')
    c.add_argument('--compiler',type=Path,help='meic to use (default BUILD_DIR/meic).')
    c.add_argument('--probe',type=Path,help='mei-scene-probe to use (default BUILD_DIR/mei-scene-probe).')
    f = q['floors']
    f.add_argument('--area',required=True,metavar='X0,Z0,X1,Z1',help='World coordinates seen from above.')
    f.add_argument('--step',type=float,default=1.0,help='Grid spacing (units, default 1).')
    f.add_argument('--layers',metavar='A,B',help='Layers on (default: those on at the start; "" for none).')
    f.add_argument('--below',type=float,metavar='Y',help='The highest floor at or below this height (default: from '
                   'above everything), as a body standing there finds it.')
    k = q['cracks']
    k.add_argument('--routes',type=Path,metavar='FILE',help='A JSON object of named routes, {"NAME": [[x, z], ...]}: '
                   'a crack within --near of one is on it.')
    k.add_argument('--near',type=float,default=3.0,help='How near a route a crack is on it (units, default 3).')
    k.add_argument('--baseline',nargs='?',const='',metavar='FILE',
                   help='Compare with the crack baseline (default NAME.cracks.json beside the recipe): exit 1 when a '
                        'crack is new.')
    k.add_argument('--write-baseline',action='store_true',help='Write the cracks found to the crack baseline '
                   '(NAME.cracks.json beside the recipe, or --baseline FILE).')
    t = q['textures']
    t.add_argument('--region',help='One region.')
    t.add_argument('--cells',action='append',default=[],metavar='I,J[;I,J...]',
                   help='Only the assets drawn in these cells (by "at" or ID), with their share of their region.')
    t.add_argument('--add',action='append',default=[],metavar='REGION:ASSET[,ASSET...]',
                   help='Count these assets as if placed in the region: names in the world\'s asset directories, or '
                        'recipe paths (NAME.asset.json). Repeatable.')
    for name,text in (('validate','Check the recipe, its cells, game data, IDs and assets, and that the pack can hold it.'),
                      ('inspect','validate, plus per-cell and per-region costs, palettes and warnings.'),
                      ('build','Build the pack, its Akari imports, the ID lock file and report.json.'),
                      ('preview','build, plus native renders of a cell per region and palette variant.')):
        cmd = sub.add_parser(name,help=text)
        cmd.add_argument('recipe',help='World recipe path, or - to read stdin (paths then resolve from the current directory).')
        cmd.add_argument('--assets',type=Path,help='Use this asset directory instead of the recipe\'s.')
        if name in ('inspect','preview'):
            cmd.add_argument('--cell',help='Report (inspect) or render (preview) one cell, by ID.')
        if name in ('build','preview'):
            cmd.add_argument('-o','--output',required=True,help='Dedicated generated-output directory.')
            if name == 'build': cmd.add_argument('--preview',action='store_true',help='Also render previews.')
            cmd.add_argument('--locked',action='store_true',help='Fail instead of changing the ID lock file.')
            cmd.add_argument('--world-checker',default='full',metavar='full|skip|N',
                             help='How the World Checker runs: full (the default), skip, or at most N sampled views. '
                                  'Recorded in report.json; refused for a world in enforce mode.')
            cmd.add_argument('--compiler',type=Path,default=ROOT/'build'/'meic')
            cmd.add_argument('--runner',type=Path,default=ROOT/'build'/'mei-headless')
            cmd.add_argument('--probe',type=Path,default=ROOT/'build'/'mei-asset-probe')
            cmd.add_argument('--cache',type=Path,help='Keep the Asset and World Checkers\' results in this directory '
                                                      'and reuse them while their inputs are unchanged.')
            cmd.add_argument('--crack-baseline',metavar='FILE|none',
                             help='The crack baseline the World Checker compares with: its cracks are listed as known, '
                                  'not failures (default NAME.cracks.json beside the recipe, when there is one).')
    return p


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == 'schema':
            jsonio.output(published(load_game(args.game) if args.game else None))
        elif args.command == 'convert':
            jsonio.output(convert(args.game,args.output,args.force))
        elif args.command == 'init':
            jsonio.output(init(args.output,args.example,args.force))
        elif args.command == 'floor':
            jsonio.output(floors(args.recipe,args.points,args.assets))
        elif args.command in ('check','floors','textures','cracks'):
            result,text = quick(args)
            if args.json: jsonio.output(result)
            else: print(text)
            return 0 if result['ok'] else 1
        elif args.command in ('build','preview'):
            jsonio.output(build(args.recipe,args.output,args.compiler.resolve(),args.runner.resolve(),
                                args.probe.resolve(),args.locked,args.assets,
                                args.command == 'preview' or args.preview,getattr(args,'cell',None),
                                args.world_checker,args.cache,args.crack_baseline))
        else:
            _,compiled = compile_source(args.recipe,args.assets)
            report = compiled.report
            if args.command == 'validate':
                report = {'ok':True,'name':report['name'],'cells':len(report['cells']),
                          'pack_bytes':report['pack']['bytes'],'ids':report['ids'],'warnings':report['warnings']}
            else:
                report = summary(report,args.cell)
            jsonio.output(report)
        return 0
    except (WorldError,AssetError,OSError,ValueError,RecursionError) as error:
        failure = {'path':getattr(error,'path','/input'),'message':str(error)}
        for key in ('file','line','column'):
            if getattr(error,key,None): failure[key] = getattr(error,key)
        if argv_wants_text(argv):
            print(f'error at {failure["path"]}' + (f' in {failure["file"]}' if 'file' in failure else '')
                  + f': {failure["message"]}')
        else:
            jsonio.output({**getattr(error,'report',{}),'ok':False,'errors':[failure]})
        return 1


def argv_wants_text(argv):
    """Whether a failed command was a quick tool asked for plain text."""
    args = sys.argv[1:] if argv is None else list(argv)
    return bool(args) and args[0] in ('check','floors','textures') and '--json' not in args


if __name__ == '__main__':
    sys.exit(main())
