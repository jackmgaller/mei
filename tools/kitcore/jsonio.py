"""JSON in and out as the kits use it: strict input (duplicate keys and oversized input are errors),
canonical bytes for hashing, and the CLI's stdout convention."""
import hashlib
import json
from pathlib import Path
import sys

from .errors import KitError

MAX_INPUT = 8*1024*1024


def parse(text, error=KitError, path='/input'):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise error(path,f'Duplicate JSON property {key!r}.')
            result[key] = value
        return result
    return json.loads(text,object_pairs_hook=unique)


def load(source, error=KitError, path='/input'):
    """A JSON file (or stdin for '-'), at most 8 MiB, with duplicate properties rejected."""
    if source == '-':
        text = sys.stdin.read(MAX_INPUT+1)
    else:
        with Path(source).open() as stream: text = stream.read(MAX_INPUT+1)
    if len(text) > MAX_INPUT: raise error(path,'Input exceeds 8 MiB.')
    return parse(text,error,path)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), allow_nan=False).encode()


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pretty(value):
    """The kits' file form: indented, a final newline."""
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def output(value):
    print(json.dumps(value,indent=2,allow_nan=False))


def write_new(path, value, force=False):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w' if force else 'x') as stream:
        stream.write(pretty(value))
