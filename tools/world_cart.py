#!/usr/bin/env python3
"""The make side of carts that use worlds (docs/WORLDKIT.md, "Using a world in a cart").

    world_cart.py build RECIPE BUILD_DIR
        Builds one world recipe with tools/mei_world.py into BUILD_DIR/worlds/<the recipe's
        folder>/, using BUILD_DIR's meic, mei-headless and mei-asset-probe (the World Checker
        finds mei-scene-probe beside meic). Prints a two-line summary, or the kit's errors one
        per line; exits 0 or 1. On success it writes build.json there (the kit's result, make's
        target) and build.d (make's dependencies: the recipe, its cells, game schema, ID lock
        file and asset recipes, and the cell and asset folders, so an added file counts too).

    world_cart.py link IMPORT_DIR BUILD_DIR RECIPE...
        Fills IMPORT_DIR, which make passes to meic with -I, with symbolic links to each built
        world's NAME.akr, NAME.world.bin and NAME.swatch and to its game's GAME.game.akr, so
        worlds of one game import a single GAME.game.akr. Fails when two worlds share a name,
        or share a game name but were built from different game schemas. Writes worlds.json
        there (make's target).

Recipe paths are relative to the repository (make runs from there). Python's standard library
only; the World Checker itself needs NumPy and reports that it did not run without it.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))


def world_dir(recipe, build):
    return Path(build)/'worlds'/Path(recipe).parent


def rel(path):
    """A path for make: relative to the current directory when inside it, spaces escaped."""
    path = os.path.abspath(path)
    try:
        path = os.path.relpath(path)
    except ValueError:
        pass
    return path.replace(' ', '\\ ')


def errors_text(recipe, result):
    lines = [f'world {recipe}: the World Kit refused it:']
    for e in result.get('errors', []):
        where = e.get('file') or recipe
        if e.get('line'): where += f':{e["line"]}:{e.get("column", 1)}'
        lines.append(f'  {where}: {e.get("path", "")}: {e.get("message", "")}')
    lines.append(f'  (python3 tools/mei_world.py validate {recipe} gives the same errors as JSON)')
    return '\n'.join(lines)


def summary(recipe, out, result):
    pack = result.get('pack', {})
    cells = pack.get('cells', 0)
    warnings = len(result.get('warnings', []))
    line = (f'world {result.get("name")}: {cells} cell{"s" if cells != 1 else ""}, {pack.get("bytes", 0):,} bytes, '
            f'{warnings} warning{"s" if warnings != 1 else ""} -> {out}')
    v = result.get('verification', {})
    if not v.get('ran'):
        reason = v.get('reason') or '; '.join(e.get('message', '') for e in v.get('errors', [])) or 'unknown'
        check = f'  World Checker did not run: {reason}'
    else:
        s = v.get('summary', {})
        peak = lambda key: s.get(key, {}).get('value', 0)
        check = (f'  World Checker ({v.get("mode")}): {s.get("views", 0)} views, '
                 f'{s.get("hard_failures", 0)} hard failures, {s.get("threshold_failures", 0)} over thresholds; '
                 f'peaks {peak("max_triangles")} tris, CPU {peak("max_draw_cpu_cycles"):,}, '
                 f'GPU {peak("max_gpu_cycles"):,} cycles; {out}/verification/world-check.json')
    return line+'\n'+check


def depfile(recipe, out):
    """The sources the build read, as a make dependency file with an empty rule for each, so a
    deleted source makes the world rebuild instead of stopping make."""
    from worldkit.world import load
    from worldkit.build import lock_path
    source = load(recipe)
    deps = [source.world_path, source.game_path, lock_path(source)]
    deps += [cs.file for cs in source.cells if cs.file]
    if 'cell_dir' in source.world:
        deps.append(source.base/source.world['cell_dir'])
    assets = (source.base/source.world['assets']).resolve()
    deps.append(assets)
    if assets.is_dir():
        deps += sorted(p for p in assets.iterdir() if p.is_file() and p.name.endswith('.asset.json'))
    names = []
    for d in deps:
        if d and Path(d).exists() and rel(d) not in names: names.append(rel(d))
    target = str(out/'build.json').replace(' ', '\\ ')   # as make names it: $(B)/worlds/...
    return f'{target}: ' + ' \\\n  '.join(names) + '\n' + ''.join(f'{n}:\n' for n in names)


def build(recipe, build_dir):
    out = world_dir(recipe, build_dir)
    out.mkdir(parents=True, exist_ok=True)
    b = Path(build_dir)
    args = [sys.executable, str(ROOT/'tools'/'mei_world.py'), 'build', recipe, '-o', str(out),
            '--compiler', str(b/'meic'), '--runner', str(b/'mei-headless'), '--probe', str(b/'mei-asset-probe')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    try:
        result = json.loads(r.stdout)
    except ValueError:
        sys.stderr.write(f'world {recipe}: tools/mei_world.py did not answer in JSON\n{r.stdout}{r.stderr}')
        return 1
    if r.returncode != 0 or not result.get('ok'):
        print(errors_text(recipe, result), file=sys.stderr)
        return 1
    (out/'build.d').write_text(depfile(recipe, out))
    (out/'build.json').write_text(json.dumps(result, indent=1)+'\n')
    print(summary(recipe, rel(out), result))
    return 0


def link(import_dir, build_dir, recipes):
    import_dir = Path(import_dir)
    import_dir.mkdir(parents=True, exist_ok=True)
    for old in import_dir.iterdir():
        if old.is_symlink(): old.unlink()
    links, worlds, games = {}, [], {}
    for recipe in recipes:
        out = world_dir(recipe, build_dir)
        result = json.loads((out/'build.json').read_text())
        name = result['name']
        game = next(f[:-len('.game.akr')] for f in result['files'] if f.endswith('.game.akr'))
        if any(w['name'] == name for w in worlds):
            other = next(w['recipe'] for w in worlds if w['name'] == name)
            print(f'{import_dir}: two worlds are named {name!r} ({other} and {recipe}); rename one.', file=sys.stderr)
            return 1
        akr = (out/f'{game}.game.akr').read_text()
        if game in games and games[game][1] != akr:
            print(f'{import_dir}: {games[game][0]} and {recipe} both use game {game!r} but were built from '
                  'different game schemas; give them one GAME.game.mochi.', file=sys.stderr)
            return 1
        games.setdefault(game, (recipe, akr))
        for f in (f'{name}.akr', f'{name}.world.bin', f'{name}.swatch', f'{game}.game.akr'):
            if (out/f).exists(): links.setdefault(f, out/f)
        worlds.append({'name': name, 'game': game, 'recipe': recipe, 'output': str(out)})
    for f, target in links.items():
        (import_dir/f).symlink_to(os.path.relpath(target.resolve(), import_dir.resolve()))
    (import_dir/'worlds.json').write_text(json.dumps({'worlds': worlds}, indent=1)+'\n')
    return 0


def main(argv):
    if len(argv) == 3 and argv[0] == 'build':
        return build(argv[1], argv[2])
    if len(argv) >= 3 and argv[0] == 'link':
        return link(argv[1], argv[2], argv[3:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
