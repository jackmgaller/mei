#!/usr/bin/env python3
"""Mei World Kit: agent-first world recipes (cells, regions, layers, game data) to world packs.

Run `python3 tools/mei_world.py schema` for the complete recipe contract (the game schema's
Mochi form is described under $defs/game x-mochi), or read docs/WORLDKIT.md. All command results
and errors are JSON on stdout; exit 0 or 1.
"""
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
EXAMPLE_WORLDS = {'room':'test_room','city':'two_districts'}


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
        elif args.command in ('build','preview'):
            jsonio.output(build(args.recipe,args.output,args.compiler.resolve(),args.runner.resolve(),
                                args.probe.resolve(),args.locked,args.assets,
                                args.command == 'preview' or args.preview,getattr(args,'cell',None),
                                args.world_checker,args.cache))
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
        jsonio.output({**getattr(error,'report',{}),'ok':False,'errors':[failure]})
        return 1


if __name__ == '__main__':
    sys.exit(main())
