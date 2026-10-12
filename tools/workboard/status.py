"""The work status store: one JSON file per agent and a JSON-lines history, in a folder every
worktree of the repository can reach.

The folder is `MEI_WORK_DIR` when set, else `mei-work/` in the repository's common git
directory (`git rev-parse --git-common-dir`), which every worktree shares and git never
commits. Layout:

    status/ID.json     the agent's current record
    status/ID.lock     taken (flock) while a writer reads, changes and replaces the record
    log/ID.jsonl       one line per change: time, the fields given, and the command

Writers replace a record atomically (a temporary file and os.replace) under the lock, so
concurrent writers never lose an update and readers never see half a file.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

STATES = ('queued', 'working', 'blocked', 'review', 'done', 'merged', 'stopped')
KINDS = ('asset', 'world', 'tool', 'design', 'other')
ITEM_STATES = ('queued', 'working', 'review', 'done', 'failed', 'dropped')
SIZES = ('small', 'medium', 'large')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
FIELDS = ('id', 'title', 'kind', 'model', 'lead', 'branch', 'worktree', 'state', 'percent',
          'step', 'items', 'questions', 'notes', 'started', 'updated', 'ended')


class StatusError(ValueError):
    pass


def now():
    return round(time.time(), 3)


def git_out(cwd, *args):
    try:
        r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def work_dir(cwd=None, env=None):
    """The status folder: MEI_WORK_DIR, else <git common dir>/mei-work."""
    env = os.environ if env is None else env
    if env.get('MEI_WORK_DIR'):
        return Path(env['MEI_WORK_DIR']).expanduser().resolve()
    cwd = Path(cwd or os.getcwd())
    common = git_out(cwd, 'rev-parse', '--git-common-dir')
    if not common:
        raise StatusError('not inside a git repository; set MEI_WORK_DIR')
    common = Path(common)
    if not common.is_absolute():
        common = cwd / common
    return common.resolve() / 'mei-work'


def check_id(agent_id):
    if not ID_RE.match(agent_id or ''):
        raise StatusError(f'bad id {agent_id!r}: letters, digits, ".", "_" and "-", at most 80')
    return agent_id


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.status_dir = self.root / 'status'
        self.log_dir = self.root / 'log'

    def ensure(self):
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def path(self, agent_id):
        return self.status_dir / f'{check_id(agent_id)}.json'

    def read(self, agent_id):
        try:
            with open(self.path(agent_id), encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return None

    def all(self):
        out = []
        if not self.status_dir.is_dir():
            return out
        for p in sorted(self.status_dir.glob('*.json')):
            try:
                with open(p, encoding='utf-8') as f:
                    rec = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(rec, dict) and rec.get('id') == p.stem:
                out.append(rec)
        return out

    def history(self, agent_id, limit=500):
        p = self.log_dir / f'{check_id(agent_id)}.jsonl'
        try:
            lines = p.read_text(encoding='utf-8').splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    @contextlib.contextmanager
    def _locked(self, agent_id):
        self.ensure()
        with open(self.status_dir / f'{check_id(agent_id)}.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _write(self, rec):
        fd, tmp = tempfile.mkstemp(dir=self.status_dir, prefix='.tmp-', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(rec, f, indent=1, sort_keys=False)
                f.write('\n')
            os.replace(tmp, self.path(rec['id']))
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def _log(self, agent_id, entry):
        line = json.dumps(entry, separators=(',', ':')) + '\n'
        fd = os.open(self.log_dir / f'{agent_id}.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode('utf-8'))
        finally:
            os.close(fd)

    def update(self, agent_id, change, op, create=False, log=None):
        """Read the record, apply change(rec) and write it back, under the lock. Returns it."""
        check_id(agent_id)
        with self._locked(agent_id):
            rec = self.read(agent_id)
            if rec is None:
                if not create:
                    raise StatusError(f'no status for {agent_id!r}; create it with "new"')
                t = now()
                rec = {'id': agent_id, 'title': agent_id, 'kind': 'other', 'model': None,
                       'lead': None, 'branch': None, 'worktree': None, 'state': 'queued',
                       'percent': None, 'step': '', 'items': [], 'questions': [], 'notes': [],
                       'started': None, 'created': t, 'updated': t, 'ended': None}
            change(rec)
            rec['updated'] = now()
            self._write(rec)
            entry = {'t': rec['updated'], 'op': op}
            entry.update(log or {})
            self._log(agent_id, entry)
            return rec


def set_state(rec, state):
    if state not in STATES:
        raise StatusError(f'state must be one of {", ".join(STATES)}')
    t = now()
    if state == 'working' and not rec.get('started'):
        rec['started'] = t
    if state in ('done', 'merged', 'stopped'):
        rec['ended'] = rec.get('ended') or t
        if state in ('done', 'merged'):
            rec['percent'] = 100
    elif rec.get('ended'):
        rec['ended'] = None
    rec['state'] = state


def set_item(rec, name, state=None, size=None, note=None):
    if state is not None and state not in ITEM_STATES:
        raise StatusError(f'item state must be one of {", ".join(ITEM_STATES)}')
    if size is not None and size not in SIZES:
        raise StatusError(f'size must be one of {", ".join(SIZES)}')
    items = rec.setdefault('items', [])
    item = next((i for i in items if i.get('name') == name), None)
    if item is None:
        item = {'name': name, 'state': 'queued', 'size': None, 'note': ''}
        items.append(item)
    if state is not None:
        item['state'] = state
    if size is not None:
        item['size'] = size
    if note is not None:
        item['note'] = note
    item['updated'] = now()
    return item


def item_percent(rec):
    items = [i for i in rec.get('items') or [] if i.get('state') != 'dropped']
    if not items:
        return None
    return round(100 * sum(i.get('state') == 'done' for i in items) / len(items))
