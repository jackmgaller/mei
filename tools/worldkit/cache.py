"""The build cache: the Asset Checker's verdicts and the World Checker's results, kept by a hash
of everything they depend on, so a world build re-checks only what changed.

`build --cache DIR` turns it on (make passes $(B)/kit-cache); without it every check runs.
Nothing in the cache is ever trusted beyond its key, and a key covers all of a result's inputs:

    Asset Checker verdict, per level of detail: the level's recipe (level_recipe(): its nodes,
    and the recipe's materials, prototypes, lighting, budget and verification policy, in their
    order; the policy's depth and perspective included, the world's where the recipe sets
    neither) and its compiled mesh's bytes, the Python source of the checker and of every tools/
    module it imports, meic, mei-asset-probe, the standard library meic compiles with and the
    depth stand-in (tests/depth_shim/), and the Python and NumPy versions.
    World Checker result: the pack's bytes, the world's name, verification settings, game probe,
    --world-checker option and runtime (depth, perspective), the source of the checker and its
    imports, meic, mei-headless, mei-scene-probe (beside meic, and the checker's defaults), the
    standard library and the depth stand-in, Python and NumPy.

A cache hit returns the stored result unchanged; tests/test_worldcache.py checks that a hit
equals a fresh run and that a change to any input misses. The checks also run in parallel
(MEI_KIT_JOBS processes, else one per core), with the results a serial run gives.
"""
import ast
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

TOOLS = Path(__file__).resolve().parents[1]
SHIM = TOOLS.parent/'tests'/'depth_shim'   # kitcore/depth.py's stand-in for stdlib/depth.akr, while it is used
VERSION = 1                       # bump to drop every existing entry
WORLD_ENTRIES = 4                 # World Checker results kept per world name

_file_hashes = {}


def file_hash(path):
    """The SHA-256 of a file's bytes, or of 'missing' for a path that is not a file."""
    path = Path(path).resolve()
    if not path.is_file():
        return 'missing:'+str(path)
    stat = path.stat()
    memo = (str(path),stat.st_size,stat.st_mtime_ns)
    if memo not in _file_hashes:
        _file_hashes[memo] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _file_hashes[memo]


def tree_hash(directory):
    """Every file under directory, by relative path and content."""
    h = hashlib.sha256()
    directory = Path(directory)
    if directory.is_dir():
        for p in sorted(directory.rglob('*')):
            if p.is_file():
                h.update(p.relative_to(directory).as_posix().encode()+b'\0'+file_hash(p).encode()+b'\n')
    return h.hexdigest()


def stdlib_dir(compiler):
    """The standard library meic compiles with: $MEI_STDLIB, else <meic's folder>/../stdlib."""
    env = os.environ.get('MEI_STDLIB')
    return Path(env) if env else Path(compiler).parent/'..'/'stdlib'


def _module_file(parts):
    base = TOOLS.joinpath(*parts) if parts else TOOLS
    for candidate in (base.with_suffix('.py'), base/'__init__.py'):
        if parts and candidate.is_file():
            return candidate
    return None


def code_files(*entries):
    """The Python files under tools/ that the entry files import, directly or not (every
    import statement counts, wherever it is), entries included, sorted."""
    seen, todo = set(), [Path(e).resolve() for e in entries]
    while todo:
        f = todo.pop()
        if f in seen: continue
        seen.add(f)
        package = list(f.relative_to(TOOLS).parent.parts)
        for node in ast.walk(ast.parse(f.read_text(),str(f))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split('.') for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = (package[:len(package)-node.level+1] if node.level else [])+(node.module.split('.') if node.module else [])
                names = [base]+[base+[a.name] for a in node.names]
            for parts in names:
                for k in range(1,len(parts)+1):            # the module and the packages above it
                    m = _module_file(parts[:k])
                    if m and m not in seen: todo.append(m)
    return sorted(seen)


def code_hash(*entries):
    h = hashlib.sha256()
    for f in code_files(*entries, TOOLS/'worldkit'/'cache.py'):
        h.update(f.relative_to(TOOLS).as_posix().encode()+b'\0'+file_hash(f).encode()+b'\n')
    return h.hexdigest()


def runtime_versions():
    try: numpy = importlib.metadata.version('numpy')
    except importlib.metadata.PackageNotFoundError: numpy = None
    return {'python':sys.version,'numpy':numpy}


def key_of(value):
    """A key from a JSON value. Object keys keep their order: a recipe's order can matter."""
    return hashlib.sha256(json.dumps(value,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _write_atomic(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(dir=path.parent,prefix='.tmp-')
    with os.fdopen(fd,'w') as stream: stream.write(text)
    os.replace(tmp,path)


def jobs():
    """Processes for parallel checks: $MEI_KIT_JOBS, else the number of cores."""
    try: return max(1,int(os.environ['MEI_KIT_JOBS']))
    except (KeyError,ValueError): return os.cpu_count() or 1


def parallel(function, tasks):
    """[function(task) for task in tasks], in worker processes when there are cores to spare,
    and here when they cannot start (a script without `if __name__ == '__main__'`)."""
    n = min(jobs(),len(tasks))
    if n > 1:
        try:
            with ProcessPoolExecutor(n) as pool:
                return list(pool.map(function,tasks))
        except (BrokenProcessPool,OSError,RuntimeError):
            pass
    return [function(task) for task in tasks]


# ---- the Asset Checker


def _verify_level(job):
    """One level's Asset Checker run, in a worker: (verdict or None, error or None)."""
    from assetkit.visibility import verify
    from assetkit.geometry import AssetError
    recipe,compiler,probe = job
    try:
        result = verify(recipe,compiler=compiler,probe=probe)
    except (AssetError,OSError,ValueError) as error:
        return None,(type(error).__name__,getattr(error,'path','/verification'),str(error))
    return {'ok':bool(result['ok']),'views':len(result.get('views',[]))},None


class AssetVerdicts:
    """Asset Checker verdicts for a set of recipes, computed in parallel and cached per level.

    verify(recipe) checks level 0 (the recipe without lod), then each level k as level_recipe(
    recipe, k), and passes when every level passes; its view count is level 0's. This runs the
    same per-level checks, each as its own job, and combines them the same way, so the verdict
    is the one verify(recipe) gives (tests/test_worldcache.py compares them)."""

    def __init__(self, directory, compiler, probe):
        self.directory = Path(directory)/'assets' if directory else None
        self.compiler = Path(compiler).resolve() if compiler else None
        self.probe = Path(probe).resolve() if probe else None
        self._common = None

    def common(self):
        if self._common is None:
            from assetkit import visibility
            c = self.compiler or visibility.ROOT/'build/meic'
            p = self.probe or visibility.ROOT/'build/mei-asset-probe'
            self._common = {'version':VERSION,'code':code_hash(visibility.__file__),
                            'meic':file_hash(c),'probe':file_hash(p),'stdlib':tree_hash(stdlib_dir(c)),
                            'depth_shim':tree_hash(SHIM),
                            **runtime_versions()}
        return self._common

    def key(self, level):
        from assetkit.compiler import compile_recipe, native_bytes
        mesh,materials,_ = compile_recipe(level)
        binary = native_bytes(mesh,materials,level.get('lighting',{}))
        return key_of({'common':self.common(),'recipe':level,'mesh':hashlib.sha256(binary).hexdigest()})

    def levels(self, recipe):
        from assetkit.compiler import level_recipe
        return [level_recipe(recipe,k) for k in range(len(recipe.get('lod',{}).get('levels',[]))+1)] \
            if 'lod' in recipe else [recipe]

    def run(self, recipes):
        """{name: (verdict, error)} for {name: recipe}: a verdict is {'ok', 'views'}; error is
        the exception verify(recipe) would raise (its first level's that could not be checked),
        and then verdict is None."""
        plan = {name:self.levels(r) for name,r in recipes.items()}
        results, todo = {}, []
        for name,levels in plan.items():
            for k,level in enumerate(levels):
                key = self.key(level) if self.directory else None
                hit = self.load(key)
                if hit is not None: results[name,k] = (hit,None)
                else: todo.append((name,k,level,key))
        if todo:
            work = [(level,self.compiler,self.probe) for _,_,level,_ in todo]
            done = parallel(_verify_level,work)
            for (name,k,_,key),(verdict,error) in zip(todo,done):
                results[name,k] = (verdict,error)
                if verdict is not None: self.save(key,verdict)
        from assetkit.geometry import AssetError
        out = {}
        for name in sorted(plan):
            verdicts = []
            for k in range(len(plan[name])):
                verdict,error = results[name,k]
                if error:
                    kind,path,message = error
                    out[name] = (None,AssetError(path,message) if kind == 'AssetError' else
                                 OSError(message) if kind == 'OSError' else ValueError(message))
                    break
                verdicts.append(verdict)
            else:
                out[name] = ({'ok':all(v['ok'] for v in verdicts),'views':verdicts[0]['views']},None)
        return out

    def load(self, key):
        if not key: return None
        try: return json.loads((self.directory/key[:2]/(key+'.json')).read_text())
        except (OSError,ValueError): return None

    def save(self, key, verdict):
        if key: _write_atomic(self.directory/key[:2]/(key+'.json'),json.dumps(verdict)+'\n')


# ---- the World Checker


def world_key(context, verify_module):
    """The key of a World Checker run on this context (worldkit.build.run_gate's)."""
    compiler = Path(context['compiler']) if context.get('compiler') else None
    tools = verify_module.default_tools()
    natives = {'compiler':compiler,'beside':compiler.parent/'mei-scene-probe' if compiler else None,
               'runner':context.get('runner'),'default_compiler':tools['compiler'],'default_probe':tools['probe']}
    std = stdlib_dir(compiler or tools['compiler'])
    return key_of({'version':VERSION,'code':code_hash(verify_module.__file__),
                   'pack':file_hash(context['pack']),
                   'settings':{k:context.get(k) for k in ('world','mode','thresholds','probe','checker','runtime')},
                   'natives':{k:file_hash(v) if v else None for k,v in natives.items()},
                   'stdlib':tree_hash(std),'depth_shim':tree_hash(SHIM),**runtime_versions()})


def checked_world(check, context, directory, verify_module):
    """check(context) (verify.check_world), or its stored result. The result's report and
    pictures (the stage's verification/) are stored with it and put back on a hit; the stored
    timing is replaced by {'cached': True}."""
    if not directory:
        return check(context)
    root = Path(directory)/'world'
    key = world_key(context,verify_module)
    entry = root/key
    stage_out = Path(context['stage'])/'verification'
    try:
        result = json.loads((entry/'result.json').read_text())
    except (OSError,ValueError):
        result = None
    if result is not None:
        if (entry/'verification').is_dir():
            shutil.copytree(entry/'verification',stage_out,dirs_exist_ok=True)
        os.utime(entry)
        result['timing'] = {'cached':True}
        return result
    result = check(context)
    if result.get('errors') or result.get('ran') is False:
        return result                       # the check did not run: nothing to keep
    # as a hit returns it: JSON's types (lists for tuples, string keys)
    timing = result.get('timing')
    result = json.loads(json.dumps(result))
    if timing is not None: result['timing'] = timing
    root.mkdir(parents=True,exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=root,prefix='.tmp-'))
    try:
        (tmp/'result.json').write_text(json.dumps(result)+'\n')
        (tmp/'world').write_text(str(context.get('world'))+'\n')
        if stage_out.is_dir():
            shutil.copytree(stage_out,tmp/'verification')
        try: tmp.rename(entry)
        except OSError: pass               # another build stored it first
    finally:
        if tmp.exists(): shutil.rmtree(tmp,ignore_errors=True)
    _prune(root,str(context.get('world')))
    return result


def _prune(root, world):
    mine = []
    for e in root.iterdir():
        try:
            if not e.name.startswith('.') and (e/'world').read_text().strip() == world:
                mine.append((e.stat().st_mtime_ns,e.name,e))
        except OSError: pass
    for _,_,e in sorted(mine,reverse=True)[WORLD_ENTRIES:]:
        shutil.rmtree(e,ignore_errors=True)
