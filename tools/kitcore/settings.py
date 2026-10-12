"""The kits' settings file, mei-kit.json: the facts the commands would otherwise be told on every
run (how the game draws, the assets' default verification policy, the build directory, the
preview's look), stated once for the recipes in its folder and the folders below it.

A command looks for the file from the recipe's folder upward, up to the repository root (this
repository's, or the first folder holding .git), and takes each setting from the nearest file
that gives it. A legacy asset-preview.json in a folder gives that folder's preview look. Where a
setting also comes from elsewhere, the order is: a command-line option, then the recipe, then the
settings file, then the environment, then the built-in default (docs/ASSETKIT-REFERENCE.md, "Settings
file"). This module finds and reads the files and resolves the build directory and native tools;
what an asset or a world makes of the rest is the kits' own business.
"""
from pathlib import Path

from .errors import KitError
from . import jsonio

FILE = 'mei-kit.json'
LOOK_FILE = 'asset-preview.json'          # the preview look alone, read for compatibility
RUNTIME = ('depth','perspective')
SECTIONS = ('runtime','verification','build_dir','preview')
ROOT = Path(__file__).resolve().parents[2]


def shown(path, root=ROOT):
    """A path as reports give it: relative to the repository, else absolute."""
    path = Path(path).resolve()
    try: return str(path.relative_to(Path(root).resolve()))
    except ValueError: return str(path)


class Settings:
    """The settings that apply to one recipe. values: {name: (value, file)} for the names
    'runtime.depth', 'runtime.perspective', 'verification', 'build_dir' and 'preview', each from
    the nearest file giving it; files: every settings file read, the nearest first."""

    def __init__(self, files=(), values=None, root=ROOT):
        self.files = list(files)
        self.values = dict(values or {})
        self.root = Path(root)

    def get(self, name, default=None):
        return self.values[name][0] if name in self.values else default

    def file(self, name):
        return self.values[name][1] if name in self.values else None

    def where(self, name):
        """The file a setting came from, as reports show it, or None."""
        return shown(self.values[name][1],self.root) if name in self.values else None

    def shown_files(self):
        return [shown(f,self.root) for f in self.files]


def folders(start, root=ROOT):
    """start and each folder above it, nearest first, up to the repository root: root, or the
    first folder holding .git, or the file system's root."""
    start, root = Path(start).resolve(), Path(root).resolve()
    out = []
    for directory in (start,*start.parents):
        out.append(directory)
        if directory == root or (directory/'.git').exists(): break
    return out


def candidates(recipe_path, root=ROOT):
    """Every mei-kit.json a recipe's settings could come from, present or not, nearest first (for
    caches that must notice a settings file appearing)."""
    if not recipe_path or recipe_path == '-': return []
    return [d/FILE for d in folders(Path(recipe_path).resolve().parent,root)]


def _fail(error, path, file, message):
    return error(path,f'{shown(file)}: {message}')


def read(file, error=KitError):
    """One mei-kit.json, its shape checked (the contents of verification and preview are checked
    by the kit that uses them)."""
    value = jsonio.load(str(file),error,'/settings')
    if not isinstance(value,dict):
        raise _fail(error,'/settings',file,'a settings file is a JSON object.')
    unknown = sorted(set(value)-set(SECTIONS))
    if unknown:
        raise _fail(error,f'/settings/{unknown[0]}',file,f'unknown setting {unknown[0]!r}; the settings are '
                    +', '.join(SECTIONS)+'.')
    runtime = value.get('runtime',{})
    if not isinstance(runtime,dict) or set(runtime)-set(RUNTIME):
        raise _fail(error,'/settings/runtime',file,'runtime is {"depth": true|false, "perspective": true|false}.')
    for key,flag in runtime.items():
        if not isinstance(flag,bool):
            raise _fail(error,f'/settings/runtime/{key}',file,f'runtime.{key} is true or false.')
    if 'verification' in value and not isinstance(value['verification'],dict):
        raise _fail(error,'/settings/verification',file,'verification is an Asset Kit verification policy (an object).')
    if 'build_dir' in value and (not isinstance(value['build_dir'],str) or not value['build_dir'].strip()):
        raise _fail(error,'/settings/build_dir',file,'build_dir is a directory path, relative to this file\'s folder.')
    if 'preview' in value:
        read_look(value['preview'],file,error,'/settings/preview')
    return value


def read_look(value, file, error=KitError, path='/look'):
    if not isinstance(value,dict) or set(value)-{'background','ground'}:
        raise _fail(error,path,file,'a look is {"background": "#rrggbb" or ["#top", "#bottom"], "ground": "#rrggbb"}.')
    return value


def find(recipe_path, root=ROOT, error=KitError):
    """The Settings for a recipe at recipe_path (none for '-', stdin)."""
    if not recipe_path or recipe_path == '-':
        return Settings(root=root)
    return find_from(Path(recipe_path).resolve().parent,root,error)


def find_from(folder, root=ROOT, error=KitError):
    """The Settings for the recipes in folder."""
    files, values = [], {}
    for directory in folders(folder,root):
        kit, look = directory/FILE, directory/LOOK_FILE
        data = {}
        if kit.is_file():
            data = read(kit,error)
            files.append(kit)
            for key in RUNTIME:
                if key in data.get('runtime',{}): values.setdefault('runtime.'+key,(data['runtime'][key],kit))
            for key in ('verification','build_dir','preview'):
                if key in data: values.setdefault(key,(data[key],kit))
        if look.is_file():
            if 'preview' in data:
                raise _fail(error,'/settings/preview',kit,f'this file and {LOOK_FILE} beside it both give the preview '
                            f'look: keep one ({FILE}\'s "preview" supersedes {LOOK_FILE}).')
            files.append(look)
            values.setdefault('preview',(read_look(jsonio.load(str(look),error,'/look'),look,error),look))
    return Settings(files,values,root)


def pick(*choices, default=None):
    """The first (value, source) whose value is not None, as {'value', 'from'}; else the default,
    from 'default'."""
    for value,source in choices:
        if value is not None: return {'value':value,'from':source}
    return {'value':default,'from':'default'}


def build_dir(given=None, settings=None, environ=None, root=ROOT):
    """(directory, how it was chosen) of the build directory: --build-dir, else the settings
    file's build_dir (relative to that file's folder), else $B (relative to the repository), else
    build/."""
    import os
    environ = os.environ if environ is None else environ
    if given is not None: return Path(given).resolve(),f'--build-dir {given}'
    if settings is not None and settings.get('build_dir') is not None:
        return ((settings.file('build_dir').parent/settings.get('build_dir')).resolve(),
                f'build_dir {settings.get("build_dir")} in {settings.where("build_dir")}')
    if environ.get('B'): return (Path(root)/environ['B']).resolve(),f'B={environ["B"]}'
    return (Path(root)/'build').resolve(),'the default, build/'
