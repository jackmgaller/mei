"""`mei_anim.py fmt`: one compact style for move files. The top-level fields one a line in a fixed
order; keys, motions and boxes one a line; anything longer than 100 columns broken by filling
lines, continuation lines aligned under the first entry. The values are unchanged (checked)."""
import json
from pathlib import Path

from .rig import AnimError

WIDTH = 100
TOP_ORDER = ['format', 'version', 'note', 'name', 'base', 'rig', 'retime', 'length', 'loop', 'air', 'travel',
             'still', 'phases', 'design', 'boxes', 'keys', 'motion', 'plant', 'marks', 'allow', 'floor_allow']
KEY_ORDER = ['at', 'remove', 'from', 'relative', 'ease', 'reach_ease', 'offset', 'floor', 'pose', 'aim', 'reach',
             'boxes', 'note']


def compact(v):
    return json.dumps(v, ensure_ascii=False, separators=(', ', ': '))


def ordered(d, order):
    return {k: d[k] for k in sorted(d, key=lambda k: (order.index(k) if k in order else len(order), ))}


def render(v, col):
    """v as JSON starting at column col: on one line if it fits, else its entries filled into
    lines (one a line when they are objects), continuation lines aligned under the first."""
    c = compact(v)
    if col+len(c) <= WIDTH or not isinstance(v, (dict, list)) or not v:
        return c
    if isinstance(v, dict):
        entries = [(compact(k)+': ', x) for k, x in v.items()]
        one_each = all(isinstance(x, dict) for x in v.values())
        out, close = '{', '}'
    else:
        entries = [('', x) for x in v]
        one_each = any(isinstance(x, dict) for x in v)
        out, close = '[', ']'
    inner = col+1
    end = inner                 # the column the text so far ends at
    for i, (prefix, x) in enumerate(entries):
        tail = close if i == len(entries)-1 else ','
        piece = prefix+compact(x)
        if i:
            if not one_each and end+1+len(piece)+len(tail) <= WIDTH:
                out += ' '+piece+tail
                end += 1+len(piece)+len(tail)
                continue
            out += '\n'+' '*inner
            end = inner
        if end+len(piece)+len(tail) <= WIDTH:
            out += piece+tail
            end += len(piece)+len(tail)
        else:
            r = prefix+render(x, end+len(prefix))+tail
            out += r
            end = end+len(r) if '\n' not in r else len(r.split('\n')[-1])
    return out


def format_move(data):
    """The file's text in the compact style."""
    d = ordered(data, TOP_ORDER)
    out = ['{']
    items = list(d.items())
    for i, (k, v) in enumerate(items):
        comma = ',' if i < len(items)-1 else ''
        head = f'  {compact(k)}: '
        if k == 'keys' and isinstance(v, list):
            v = [ordered(x, KEY_ORDER) if isinstance(x, dict) else x for x in v]
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v) and len(head)+len(compact(v)) > WIDTH:
            out.append(head+'[')
            for j, x in enumerate(v):
                out.append('    '+render(x, 4)+(',' if j < len(v)-1 else ''))
            out.append('  ]'+comma)
        elif isinstance(v, dict) and v and all(isinstance(x, dict) for x in v.values()) and \
                len(head)+len(compact(v)) > WIDTH:
            out.append(head+'{')
            sub = list(v.items())
            for j, (sk, sv) in enumerate(sub):
                h = f'    {compact(sk)}: '
                out.append(h+render(sv, len(h))+(',' if j < len(sub)-1 else ''))
            out.append('  }'+comma)
        else:
            out.append(head+render(v, len(head))+comma)
    out.append('}')
    return '\n'.join(out)+'\n'


def fmt(paths, check=False):
    """Formats each file (check: only reports). Returns [paths that changed (or would)]."""
    changed = []
    for path in paths:
        path = Path(path)
        text = path.read_text()
        try:
            data = json.loads(text)
        except ValueError as error:
            raise AnimError('/input', f'{path}: not JSON: {error}') from error
        new = format_move(data)
        if json.loads(new) != data:
            raise AnimError('/input', f'{path}: formatting would change its values (a bug in fmt); left alone.')
        if new != text:
            changed.append(str(path))
            if not check:
                path.write_text(new)
    return changed
