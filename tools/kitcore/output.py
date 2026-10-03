"""Staged outputs: a build writes everything into a staging directory inside the output
directory, and only when every step has succeeded replaces the previous files, so a failure
leaves the last good build intact."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile

from .errors import KitError


@contextmanager
def staging(directory, prefix):
    """A fresh staging directory inside directory (created if needed), removed afterwards."""
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=prefix,dir=directory) as tmp:
        yield Path(tmp)


def guard(directory, names, sources, what='Output'):
    """Refuses outputs that would overwrite one of the source files (paths)."""
    directory = Path(directory).resolve()
    sources = {Path(s).resolve() for s in sources if s and s != '-'}
    for name in names:
        if (directory/name).resolve() in sources:
            raise KitError('/output',f'{what} would overwrite the source recipe. Use a separate output directory.')


def commit(stage, directory):
    """Moves every top-level entry of stage into directory, replacing what is there. Returns
    the sorted names."""
    stage, directory = Path(stage), Path(directory)
    names = sorted(p.name for p in stage.iterdir())
    for name in names:
        target = directory/name
        if (stage/name).is_dir() and target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        (stage/name).replace(target)
    return names
