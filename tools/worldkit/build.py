"""`build`: compile a world, run the gates, and write its outputs staged, replacing the previous
build only when everything succeeded.

Outputs for a world named NAME (game GAME) in the output directory:

    NAME.world.bin      the pack (docs/WORLDPACK.md)
    NAME.akr            embed, loader, region/variant/layer/entity/saved-bit constants
    GAME.game.akr       the game's entity types: numbers, parameter structs, enums
    NAME.swatch         the 8-byte palette swatch row (when any material is palette-backed)
    NAME.ids.json       a copy of the ID lock file (the original is written beside the recipe)
    source/             the world file, its cell files, the game schema and every asset recipe used
    report.json         per cell and region costs, palettes, IDs, asset hashes, warnings, gates
    verification/       the World Checker's report (world-check.json) and pictures of its worst views
    preview/            (preview, or build --preview) per region and palette variant, one cell
                        rendered natively, and contact.png
"""
from pathlib import Path

from kitcore import jsonio, output as staged
from . import ids
from .schema import WorldError
from .world import load, compile_world


def lock_path(source):
    base = source.world_path.parent if source.world_path else Path.cwd()
    return base/f'{source.world["name"]}.ids.json'


def compile_source(path, assets_dir=None):
    source = load(path)
    lock = ids.load(lock_path(source),source.world['name'])
    return source, compile_world(source,lock,assets_dir)


def checker_option(value):
    """build()'s `checker`: 'full' (the default), 'skip', or a number of views (an int >= 1)."""
    if value is None or value == 'full': return 'full'
    if value == 'skip': return 'skip'
    text = str(value).strip()
    if isinstance(value, bool) or not text.isdigit() or int(text) < 1:
        raise WorldError('/arguments', f'The World Checker option is full, skip or a number of views (1 or more), '
                         f'not {value!r}.')
    return int(text)


def run_gate(context):
    """The seam for the World Checker (tools/worldkit/verify.py, built separately). It receives
    the staged outputs and the world's settings and returns a result dict with at least `ok`.
    Thresholds are per-world settings (the recipe's verification.thresholds, defaults from the
    checker); the mode is "report" (the default: findings are recorded, nothing fails) or
    "enforce". Until the checker is installed the build records that it did not run."""
    try:
        from . import verify
    except ImportError:
        return {'ran':False,'ok':True,'mode':context['mode'],'reason':'The World Checker (worldkit.verify) is not installed.'}
    if not hasattr(verify,'check_world'):
        return {'ran':False,'ok':True,'mode':context['mode'],'reason':'worldkit.verify has no check_world(context).'}
    if context.get('checker') == 'skip':
        # Only on request (build --world-checker skip), and recorded as such in report.json.
        return {'ran':False,'ok':None,'mode':context['mode'],'skipped':True,
                'reason':'Skipped on request (--world-checker skip): this build is not verified.'}
    result = dict(verify.check_world(context))
    result.setdefault('ran',True)
    result['mode'] = context['mode']
    if isinstance(context.get('checker'),int):
        result['reduced'] = {'max_views':context['checker'],
                             'reason':f'A reduced sample on request (--world-checker {context["checker"]}), '
                                      'not the full check.'}
    return result


def build(path, directory, compiler=None, runner=None, probe=None, locked=False, assets_dir=None, preview=False,
          cell=None, checker='full'):
    """`checker` is how the World Checker runs: 'full' (the world's own settings), 'skip', or
    a number of views to sample at most, for a quick check. A world whose recipe says
    verification.mode "enforce" builds only with the full check."""
    checker = checker_option(checker)
    source, compiled = compile_source(path,assets_dir)
    settings = source.world.get('verification',{})
    if checker != 'full' and settings.get('mode') == 'enforce':
        raise WorldError('/verification/mode','This world enforces the World Checker, so it builds only with the full '
                         f'check, not --world-checker {checker}. Build without the option, or set the mode to "report".')
    name, game = source.world['name'], source.game['name']
    if locked and compiled.lock_changes:
        raise WorldError('/cells',f'The ID lock file would change ({compiled.lock_changes}); --locked forbids it. '
                         'Build without --locked and commit NAME.ids.json.')
    # Every asset's own verification policy must pass before anything is written.
    compiled.library.verify(compiler,probe)
    for asset_name,asset in compiled.library.assets.items():
        compiled.report['assets'][asset_name] = asset.summary()
    files = {f'{name}.world.bin':compiled.pack,f'{name}.akr':compiled.akr.encode(),
             f'{game}.game.akr':compiled.game_akr.encode(),f'{name}.ids.json':jsonio.pretty(compiled.lock).encode()}
    if compiled.swatch: files[f'{name}.swatch'] = compiled.swatch
    snapshot = {'source/'+(source.world_path.name if source.world_path else f'{name}.world.json'):jsonio.pretty(source.world).encode(),
                # The game schema exactly as written, comments included. report.json's game_sha256
                # is the hash of its JSON form, which this file parses to.
                'source/'+source.game_path.name:source.game_text}
    for cs in source.cells:
        if cs.file:
            snapshot['source/'+source.world['cell_dir'].strip('/')+'/'+Path(cs.file).name] = jsonio.pretty(cs.recipe).encode()
    for asset_name,asset in sorted(compiled.library.assets.items()):
        snapshot[f'source/{Path(source.world["assets"]).name or "assets"}/{asset_name}.asset.json'] = jsonio.pretty(asset.recipe).encode()
    sources = ([source.world_path,source.game_path,lock_path(source)]+[cs.file for cs in source.cells]
               +[a.file for a in compiled.library.assets.values()])
    directory = Path(directory).resolve()
    staged.guard(directory,list(files)+['report.json','source','preview'],sources,error=WorldError)
    for s in sources:
        if s and Path(s).resolve().is_relative_to(directory/'source'):
            raise WorldError('/output','The output directory\'s source/ would overwrite the recipe. Use a separate output directory.')
    with staged.staging(directory,'.mei-world-') as stage:
        for rel,data in {**files,**snapshot}.items():
            (stage/rel).parent.mkdir(parents=True,exist_ok=True)
            (stage/rel).write_bytes(data)
        context = {'world':name,'stage':str(stage),'pack':str(stage/f'{name}.world.bin'),'akr':str(stage/f'{name}.akr'),
                   'mode':settings.get('mode','report'),'thresholds':settings.get('thresholds',{}),
                   'probe':source.game['probe'],'report':compiled.report,'checker':checker,
                   'compiler':str(compiler) if compiler else None,'runner':str(runner) if runner else None}
        gate = run_gate(context)
        # Wall-clock timings would make report.json differ between identical builds.
        timing = gate.pop('timing',None)
        # report.json keeps the checker's summary and failures; its row per sampled view (over
        # a megabyte for the example city) stays in the checker's own verification/world-check.json.
        compiled.report['verification'] = {k:v for k,v in gate.items() if k != 'views'}
        if 'views' in gate: compiled.report['verification']['views_report'] = 'verification/world-check.json'
        if context['mode'] == 'enforce' and not gate['ok']:
            failure = directory/'verification.failed.json'
            failure.write_text(jsonio.pretty(gate))
            raise WorldError('/verification','Export blocked by the World Checker; see verification.failed.json.')
        if preview:
            from .preview import render
            compiled.report['preview'] = render(stage,source,compiled,compiler,runner,cell)
        (stage/'report.json').write_text(jsonio.pretty(compiled.report))
        generated = staged.commit(stage,directory)
    # The lock beside the recipe changes only once the build that needs it has been published.
    if compiled.lock_changes or not lock_path(source).exists():
        lock_path(source).write_text(jsonio.pretty(compiled.lock))
    result = dict(compiled.report,output=str(directory),files=generated,lock=str(lock_path(source)))
    if timing: result['verification_timing'] = timing
    return result
