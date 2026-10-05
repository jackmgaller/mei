"""What the workboard can tell without being told: worktrees and branches from git, and the
kits' outputs found in each worktree, merged with the status records (status.py).

snapshot(cfg) returns the whole board as one JSON-able dict; serve.py caches and serves it.
Everything here only reads: git plumbing commands (`worktree list`, `for-each-ref`, `log`,
`status`) and files under the worktrees.
"""
from dataclasses import dataclass, field
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import time

from . import status as st

IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
               '.webp': 'image/webp'}
SKIP_BUILD_DIRS = {'src', 'obj', 'web', 'reference_renderer', 'cart-worlds', 'carts', 'tests',
                   'verification-failed', 'node_modules', '.git'}
LOCK_RE = re.compile(r'\(pid (\d+)')


@dataclass
class Config:
    repo: Path
    work_dir: Path | None = None
    base: str = 'main'
    stale_minutes: float = 20
    since_hours: float = 12
    branches: list = field(default_factory=list)   # glob patterns; empty: every branch
    include_main: bool = False
    show_all: bool = False


def git(cwd, *args, timeout=30):
    try:
        r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def mtime(p):
    try:
        return os.stat(p).st_mtime
    except OSError:
        return None


def birth(p):
    try:
        s = os.stat(p)
    except OSError:
        return None
    return getattr(s, 'st_birthtime', None) or s.st_mtime


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def common_dir(repo):
    out = git(repo, 'rev-parse', '--git-common-dir')
    if out is None:
        raise st.StatusError(f'{repo} is not a git repository')
    p = Path(out.strip())
    return (p if p.is_absolute() else Path(repo) / p).resolve()


def list_worktrees(repo):
    """git worktree list --porcelain, with each worktree's admin directory, lock and times."""
    out = git(repo, 'worktree', 'list', '--porcelain') or ''
    common = common_dir(repo)
    wts = []
    cur = None
    for line in out.splitlines() + ['']:
        if not line:
            if cur:
                wts.append(cur)
            cur = None
            continue
        key, _, val = line.partition(' ')
        if key == 'worktree':
            cur = {'path': val, 'head': None, 'branch': None, 'locked': None, 'prunable': False,
                   'bare': False, 'detached': False}
        elif cur is None:
            continue
        elif key == 'HEAD':
            cur['head'] = val
        elif key == 'branch':
            cur['branch'] = val.removeprefix('refs/heads/')
        elif key == 'locked':
            cur['locked'] = val or 'locked'
        elif key == 'prunable':
            cur['prunable'] = True
        elif key == 'bare':
            cur['bare'] = True
        elif key == 'detached':
            cur['detached'] = True
    for i, wt in enumerate(wts):
        wt['main'] = i == 0
        admin = common if i == 0 else None
        if i:
            try:
                text = (Path(wt['path']) / '.git').read_text().strip()
                if text.startswith('gitdir:'):
                    admin = Path(text[7:].strip())
            except OSError:
                pass
            if admin is None:
                admin = common / 'worktrees' / Path(wt['path']).name
        wt['admin'] = str(admin)
        wt['created'] = birth(Path(admin) / 'commondir') if i else None
        # not the index: `git status` (ours included) rewrites it without any work being done
        acts = [mtime(Path(admin) / n) for n in ('HEAD', 'logs/HEAD')]
        wt['git_activity'] = max([a for a in acts if a] or [0]) or None
        pid = None
        if wt['locked']:
            m = LOCK_RE.search(wt['locked'])
            pid = int(m.group(1)) if m else None
        wt['lock_pid'] = pid
        wt['running'] = bool(wt['locked'] and pid and pid_alive(pid))
    return wts


def branch_tips(repo):
    out = git(repo, 'for-each-ref', 'refs/heads',
              '--format=%(refname:short)%09%(objectname)%09%(committerdate:unix)%09%(subject)') or ''
    tips = {}
    for line in out.splitlines():
        parts = line.split('\t', 3)
        if len(parts) == 4:
            tips[parts[0]] = {'sha': parts[1], 't': int(parts[2] or 0), 'subject': parts[3]}
    return tips


class Cache:
    """Per-path JSON and per-commit git results, kept between snapshots."""

    def __init__(self):
        self.json = {}
        self.commits = {}

    def load_json(self, path, limit=16 << 20):
        try:
            s = os.stat(path)
        except OSError:
            return None
        key = (s.st_mtime_ns, s.st_size)
        hit = self.json.get(path)
        if hit and hit[0] == key:
            return hit[1]
        data = None
        if s.st_size <= limit:
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, ValueError, UnicodeDecodeError):
                data = None
        self.json[path] = (key, data)
        return data


def own_commits(repo, cache, branch, tips, base):
    """The commits on `branch` that no other branch has, unless that branch is built on this one:
    commits reachable from the tip but not from the base or from any branch that does not contain
    the tip. Returns (commits, base contains tip); each commit lists the paths it touched."""
    tip = tips[branch]['sha']
    key = (branch, tip, tuple(sorted((b, t['sha']) for b, t in tips.items())), base)
    if key in cache.commits:
        return cache.commits[key]
    contains = set((git(repo, 'for-each-ref', '--contains', tip, '--format=%(refname:short)',
                        'refs/heads') or '').split())
    exclude = [t['sha'] for b, t in tips.items() if b not in contains and b != branch]
    if base in tips and base != branch and base not in contains:
        exclude.append(tips[base]['sha'])
    exclude = sorted(set(exclude))
    out = git(repo, 'log', '-n', '300', '--format=%x1e%H%x09%ct%x09%s', '--name-only', tip,
              '--not', *exclude) or ''
    commits = []
    for chunk in out.split('\x1e')[1:]:
        lines = chunk.strip('\n').split('\n')
        sha, t, subject = (lines[0].split('\t', 2) + ['', ''])[:3]
        names = [n for n in lines[1:] if n]
        commits.append({'sha': sha[:9], 't': int(t or 0), 'subject': subject, 'paths': names})
    merged = bool(base in tips and base != branch and base in contains)
    res = (commits, merged)
    cache.commits[key] = res
    return res


def dirty_files(path):
    out = git(path, '--no-optional-locks', 'status', '--porcelain=v1', '-z', '-uall', '--no-renames', timeout=60)
    if out is None:
        return []
    res = []
    for entry in out.split('\0'):
        if len(entry) > 3:
            res.append({'code': entry[:2].strip() or '?', 'path': entry[3:]})
    return res


def size_class(bounds):
    try:
        ext = max(hi - lo for lo, hi in zip(bounds['min'], bounds['max']))
    except (KeyError, TypeError, ValueError):
        return None, None
    return ('small' if ext <= 2 else 'medium' if ext <= 8 else 'large'), round(ext, 2)


def scan_build_outputs(wt_path, cache, max_depth=5, budget=4000):
    """report.json (Asset Kit, World Kit) and world-check.json under the worktree's build*
    directories."""
    found = []
    root = Path(wt_path)
    try:
        tops = [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False) and e.name.startswith('build')]
    except OSError:
        return found
    seen = 0
    stack = [(e.path, 1) for e in tops]
    while stack and seen < budget:
        d, depth = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            seen += 1
            if e.is_dir(follow_symlinks=False):
                if depth < max_depth and e.name not in SKIP_BUILD_DIRS and not e.name.endswith('.dSYM'):
                    stack.append((e.path, depth + 1))
            elif e.name in ('report.json', 'world-check.json'):
                data = cache.load_json(e.path)
                if isinstance(data, dict) and data.get('format') in (
                        'mei-asset-report', 'mei-world-report', 'mei-world-check'):
                    found.append((e.path, data, mtime(e.path)))
    return found


def rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return None


def asset_from_report(path, data, t, wt):
    d = Path(path).parent
    size, extent = size_class(data.get('bounds'))
    ver = data.get('verification')
    verify = None
    verdict = None
    if isinstance(ver, dict):
        verify = 'pass' if ver.get('ok') else 'fail'
        verdict = ver.get('verdict')
    elif (d / 'verification.failed.json').exists():
        verify = 'fail'
    budget = (data.get('budget') or {}).get('triangles')
    gpu = None
    prev = data.get('preview') or {}
    for v in ((prev.get('cameras') or {}).get('views') or []) + (prev.get('views') or []):
        c = (v or {}).get('cost') or {}
        p = c.get('asset_gpu_frame_percent')
        if isinstance(p, (int, float)):
            gpu = max(gpu or 0, p)
    images = {}
    for n in ('contact.png', 'cameras.png'):
        if (d / n).is_file():
            images[n[:-4]] = rel(d / n, wt)
    if 'contact' not in images and (d / 'verification-failed/preview/contact.png').is_file():
        images['contact'] = rel(d / 'verification-failed/preview/contact.png', wt)
    return {'name': data.get('name'), 'triangles': data.get('triangles'), 'vertices': data.get('vertices'),
            'budget': budget, 'verify': verify, 'verdict': verdict, 'size': size, 'extent': extent,
            'gpu_percent': gpu, 'report': rel(path, wt), 'report_time': t, 'images': images,
            'warnings': len(data.get('warnings') or []), 'ok': data.get('ok')}


def recipe_info(wt, relpath, cache):
    data = cache.load_json(str(Path(wt) / relpath), limit=8 << 20)
    name = Path(relpath).name.removesuffix('.asset.json')
    info = {'name': name, 'recipe': relpath, 'budget': None, 'images': {}}
    if isinstance(data, dict):
        info['name'] = data.get('name') or name
        info['budget'] = (data.get('budget') or {}).get('triangles')
    d = Path(wt) / Path(relpath).parent
    for sub in ('preview', '.'):
        for n in ('contact.png', 'cameras.png'):
            p = d / sub / n
            if n[:-4] not in info['images'] and p.is_file():
                info['images'][n[:-4]] = rel(p, wt)
    return info


def classify(files):
    def has(pred):
        return any(pred(f) for f in files)
    if has(lambda f: f.endswith(('.world.json', '.cell.json'))):
        return 'world'
    if has(lambda f: f.endswith('.asset.json')):
        return 'asset'
    if has(lambda f: f.startswith(('tools/', 'src/', 'tests/', 'stdlib/'))):
        return 'tool'
    if has(lambda f: f.startswith('docs/') or f.endswith(('.md', '.html'))):
        return 'design'
    return None


def level_of(relpath, world_dirs):
    best = None
    for wd in world_dirs:
        if relpath.startswith(wd + '/') and (best is None or len(wd) > len(best)):
            best = wd
    if best:
        return best
    parts = relpath.split('/')
    if 'assets' in parts:
        i = parts.index('assets')
        return '/'.join(parts[:i]) or 'assets'
    return '/'.join(parts[:-2]) or '.'


def snapshot(cfg, cache=None):
    cache = cache or Cache()
    t0 = time.time()
    repo = Path(cfg.repo).resolve()
    work = Path(cfg.work_dir) if cfg.work_dir else st.work_dir(repo)
    store = st.Store(work)
    records = store.all()
    wts = list_worktrees(repo)
    tips = branch_tips(repo)
    main_wt = wts[0]['path'] if wts else str(repo)
    stale_s = cfg.stale_minutes * 60
    window = cfg.since_hours * 3600

    by_branch = {r['branch']: r for r in records if r.get('branch')}
    by_wt = {str(Path(r['worktree']).resolve()): r for r in records if r.get('worktree')}
    used_records = set()

    cards = []
    keys = set()
    for wt in wts:
        if wt['bare'] or wt['prunable']:
            continue
        if wt['main'] and not cfg.include_main:
            continue
        b = wt['branch']
        rec = by_wt.get(str(Path(wt['path']).resolve())) or (by_branch.get(b) if b else None)
        if cfg.branches and not rec and not any(fnmatch.fnmatch(b or '', g) for g in cfg.branches):
            continue
        tip_t = tips.get(b, {}).get('t') if b else None
        cheap = max([x for x in (wt['git_activity'], tip_t, wt['created']) if x] or [0])
        if not (rec or wt['running'] or cfg.show_all or time.time() - cheap < window):
            continue
        key = Path(wt['path']).name
        while key in keys:
            key += '_'
        keys.add(key)
        if rec:
            used_records.add(rec['id'])
        cards.append(build_card(repo, cfg, cache, wt, key, rec, tips, stale_s))

    for rec in records:
        if rec['id'] in used_records:
            continue
        key = rec['id']
        while key in keys:
            key += '_'
        keys.add(key)
        cards.append(build_card(repo, cfg, cache, None, key, rec, tips, stale_s))

    worlds = find_worlds(main_wt, cards, cache)
    world_dirs = [str(Path(w['path']).parent) for w in worlds]
    assets = []
    questions = []
    for c in cards:
        for a in c.pop('_assets'):
            a['card'] = c['key']
            a['level'] = level_of(a['recipe'], world_dirs) if a.get('recipe') else (
                'build output' if a.get('report') else None)
            assets.append(a)
        for q in c.get('questions') or []:
            questions.append({'card': c['key'], 'title': c['title'], 'model': c.get('model'), **q})
    questions.sort(key=lambda q: (q.get('answer') is not None, -(q.get('asked') or 0)))
    cards.sort(key=lambda c: -(c.get('activity') or 0))
    return {'generated': time.time(), 'took': round(time.time() - t0, 2), 'repo': str(repo),
            'work_dir': str(work), 'base': cfg.base, 'stale_minutes': cfg.stale_minutes,
            'since_hours': cfg.since_hours, 'worktrees_total': len(wts), 'agents': cards,
            'assets': assets, 'worlds': worlds, 'questions': questions,
            'states': list(st.STATES), 'kinds': list(st.KINDS)}


def build_card(repo, cfg, cache, wt, key, rec, tips, stale_s):
    now = time.time()
    branch = (wt or {}).get('branch') or (rec or {}).get('branch')
    path = (wt or {}).get('path') or (rec or {}).get('worktree')
    if path and not Path(path).is_dir():
        path = None
    g = {'head': None, 'commits': [], 'files': [], 'merged': False, 'dirty': [], 'locked': None,
         'running': False, 'last_commit': None}
    if wt:
        g['head'] = (wt['head'] or '')[:9]
        g['locked'] = wt['locked']
        g['running'] = wt['running']
    created = (wt or {}).get('created')
    if branch in tips:
        commits, merged = own_commits(repo, cache, branch, tips, cfg.base)
        # commits older than the worktree were there before the agent started
        if created:
            commits = [c for c in commits if c['t'] >= created - 60]
        files = sorted({f for c in commits for f in c['paths']})
        g.update(commits=[{k: v for k, v in c.items() if k != 'paths'} | {'files': len(c['paths'])}
                          for c in commits[:50]],
                 commit_count=len(commits), files=files, merged=merged)
        g['last_commit'] = {'t': tips[branch]['t'], 'subject': tips[branch]['subject']}
    if path and wt:
        g['dirty'] = dirty_files(path)
    dirty_paths = [d['path'] for d in g['dirty']]
    dirty_t = [mtime(Path(path) / p) for p in dirty_paths[:400]] if path else []
    outputs = scan_build_outputs(path, cache) if path else []

    started = (rec or {}).get('started') or (wt or {}).get('created') or (rec or {}).get('created')
    own_t = g['commits'][0]['t'] if g['commits'] else None
    activity = max([x for x in [(wt or {}).get('git_activity'), own_t, (rec or {}).get('updated')]
                    + dirty_t + [o[2] for o in outputs] if x] or [started or 0])

    # inferred state
    if g['merged'] and g['last_commit'] and started and g['last_commit']['t'] >= started - 60:
        inferred = 'merged'
    elif g['running']:
        inferred = 'working'
    elif g['locked']:
        inferred = 'stopped'
    elif g['commits'] and not dirty_paths:
        inferred = 'review'
    elif now - activity < stale_s:
        inferred = 'working'
    elif g['commits'] or dirty_paths:
        inferred = 'review'
    else:
        inferred = 'stopped'

    state = (rec or {}).get('state') or inferred
    if rec and state in ('working', 'queued', 'blocked') and inferred == 'merged':
        state = 'merged'
    all_files = sorted(set(g['files']) | set(dirty_paths))
    kind = (rec or {}).get('kind')
    if not kind or kind == 'other':
        kind = classify(all_files) or (
            'asset' if any(o[1].get('format') == 'mei-asset-report' for o in outputs) else kind or 'other')
    active = state in ('queued', 'working', 'blocked')
    stale = bool(active and state != 'queued' and now - activity > stale_s)

    # assets: recipes changed on the branch, the Asset Kit's reports, the reported items
    assets = {}
    committed = set(g['files'])
    for f in all_files:
        if f.endswith('.asset.json') and not f.startswith('build') and path:
            if not (Path(path) / f).is_file():
                continue
            info = recipe_info(path, f, cache)
            info.update(committed=f in committed, dirty=f in dirty_paths, source='recipe')
            assets.setdefault(info['name'], info)
    reports = sorted((o for o in outputs if o[1].get('format') == 'mei-asset-report'), key=lambda o: o[2] or 0)
    for p, data, t in reports:
        a = asset_from_report(p, data, t, path)
        if not a['name']:
            continue
        cur = assets.get(a['name'])
        if cur is None:
            a.update(source='build', committed=False, dirty=False, recipe=None)
            assets[a['name']] = a
        else:
            imgs = dict(cur.get('images') or {})
            imgs.update(a['images'])
            budget = cur.get('budget') or a['budget']
            cur.update(a)
            cur['images'], cur['budget'] = imgs, budget
    items = (rec or {}).get('items') or []
    for it in items:
        a = assets.get(it['name'])
        if a is not None:
            a['item_state'] = it.get('state')
            if it.get('size'):
                a['size'] = it['size']
    if kind == 'asset':
        for it in items:
            if it['name'] not in assets:
                assets[it['name']] = {'name': it['name'], 'source': 'item', 'item_state': it.get('state'),
                                      'size': it.get('size'), 'images': {}, 'recipe': None}
    asset_list = []
    for a in assets.values():
        a['collision'] = a['name'].endswith('_col')
        if a.get('verify') == 'pass':
            a['state'] = 'verified'
        elif a.get('verify') == 'fail' or a.get('ok') is False:
            a['state'] = 'failing'
        elif a.get('report'):
            a['state'] = 'built'
        else:
            a['state'] = 'recipe' if a.get('recipe') else (a.get('item_state') or 'queued')
        if a.get('item_state') in ('done', 'dropped', 'failed'):
            a['state'] = {'done': a['state'] if a['state'] == 'verified' else 'done'}.get(a['item_state'], a['item_state'])
        for k, v in list(a['images'].items()):
            a['images'][k] = f'/img?w={key}&p={v}' if v and path else None
        asset_list.append(a)
    asset_list.sort(key=lambda a: (a['collision'], a['name']))

    world_reports = []
    for p, data, t in outputs:
        if data.get('format') == 'mei-world-report':
            world_reports.append(world_report_summary(p, data, t, path))
        elif data.get('format') == 'mei-world-check':
            world_reports.append({'name': None, 'check': rel(p, path), 'ok': data.get('ok'), 'time': t,
                                  'failures': len(data.get('failures') or [])})

    percent = (rec or {}).get('percent')
    if percent is None:
        percent = st.item_percent(rec or {})
    title = (rec or {}).get('title')
    if not title or title == (rec or {}).get('id'):
        title = (rec or {}).get('title') or branch or key
    ended = (rec or {}).get('ended')
    if not ended and state in ('done', 'merged', 'stopped', 'review'):
        ended = own_t or activity
    group = (branch or key).split('-')[0].split('/')[-1] if branch else (rec or {}).get('lead') or 'other'
    return {
        'key': key, 'id': (rec or {}).get('id'), 'reported': rec is not None,
        'title': title, 'kind': kind, 'model': (rec or {}).get('model'), 'lead': (rec or {}).get('lead'),
        'branch': branch, 'worktree': path, 'group': group,
        'state': state, 'inferred_state': inferred, 'state_source': 'reported' if rec and rec.get('state') else 'inferred',
        'percent': percent, 'step': (rec or {}).get('step') or '',
        'items': items, 'questions': (rec or {}).get('questions') or [], 'notes': (rec or {}).get('notes') or [],
        'started': started, 'ended': ended, 'updated': (rec or {}).get('updated'), 'activity': activity,
        'stale': stale, 'git': {**g, 'dirty': g['dirty'][:60], 'dirty_count': len(g['dirty']),
                                'files': g['files'][:200], 'file_count': len(g['files'])},
        'touched': all_files[:2000], 'world_reports': world_reports, '_assets': asset_list,
        'asset_count': len([a for a in asset_list if not a['collision']]),
    }


def world_report_summary(p, data, t, wt):
    cells = {}
    for c in data.get('cells') or []:
        tri = c.get('triangles') or {}
        cells[c.get('id')] = {'triangles': tri.get('most') if isinstance(tri, dict) else tri,
                              'placements': c.get('placements'), 'entities': c.get('entities'),
                              'file': c.get('file')}
    ver = data.get('verification') or {}
    return {'name': data.get('name'), 'report': rel(p, wt), 'time': t, 'ok': data.get('ok'),
            'check_ok': ver.get('ok') if isinstance(ver, dict) else None,
            'cells': cells, 'pack_bytes': (data.get('pack') or {}).get('bytes')}


def find_worlds(main_wt, cards, cache):
    """Every world recipe in the main checkout and on the cards' branches, with its cells and
    which card has touched which cell file."""
    paths = {}
    out = git(main_wt, 'ls-files', '*.world.json') or ''
    for f in out.split():
        paths.setdefault(f, None)
    for c in cards:
        for f in c['touched']:
            if f.endswith('.world.json') and not f.startswith('build'):
                paths[f] = c
    worlds = []
    for wpath, owner in paths.items():
        src_root = owner['worktree'] if owner and owner.get('worktree') else main_wt
        recipe = cache.load_json(str(Path(src_root) / wpath))
        if not isinstance(recipe, dict) or recipe.get('format') != 'mei-world':
            continue
        wdir = str(Path(wpath).parent)
        cell_dir = str(Path(wdir) / recipe['cell_dir']) if recipe.get('cell_dir') else None
        cells = {}

        def add_cells(root, src):
            if not cell_dir:
                return
            try:
                names = sorted(os.listdir(Path(root) / cell_dir))
            except OSError:
                return
            for n in names:
                if not n.endswith('.cell.json'):
                    continue
                f = f'{cell_dir}/{n}'
                if f in cells:
                    continue
                d = cache.load_json(str(Path(root) / f))
                if isinstance(d, dict) and isinstance(d.get('at'), list) and len(d['at']) == 2:
                    cells[f] = {'id': d.get('id') or n[:-10], 'at': d['at'], 'region': d.get('region'),
                                'file': f, 'placements': len(d.get('placements') or []),
                                'entities': len(d.get('entities') or []), 'touched_by': [], 'source': src}
        add_cells(main_wt, 'main')
        for c in cards:
            if c.get('worktree') and any(f.startswith(cell_dir + '/') for f in c['touched'] if cell_dir):
                add_cells(c['worktree'], c['key'])
        if not cells and isinstance(recipe.get('cells'), list):
            for d in recipe['cells']:
                if isinstance(d, dict) and isinstance(d.get('at'), list):
                    cells[wpath + '#' + str(d.get('id'))] = {
                        'id': d.get('id'), 'at': d['at'], 'region': d.get('region'), 'file': wpath,
                        'placements': len(d.get('placements') or []), 'entities': len(d.get('entities') or []),
                        'touched_by': [], 'source': 'main'}
        other = []
        report = None
        for c in cards:
            dirty = {d['path'] for d in c['git']['dirty']}
            mine = [f for f in c['touched'] if f == wpath or f.startswith(wdir + '/')]
            for f in mine:
                if f in cells:
                    cells[f]['touched_by'].append({'card': c['key'], 'state': c['state'],
                                                   'how': 'uncommitted' if f in dirty else 'committed'})
            if mine:
                other.append({'card': c['key'], 'files': len(mine),
                              'cells': sum(1 for f in mine if f in cells),
                              'assets': sum(1 for f in mine if f.endswith('.asset.json'))})
            for r in c.get('world_reports') or []:
                if r.get('name') == recipe.get('name') and (report is None or (r['time'] or 0) > (report['time'] or 0)):
                    report = {**r, 'card': c['key']}
        if report:
            for cell in cells.values():
                rc = report['cells'].get(cell['id'])
                if rc:
                    cell['triangles'] = rc.get('triangles')
        worlds.append({'name': recipe.get('name') or Path(wpath).stem, 'path': wpath,
                       'cell_size': (recipe.get('grid') or {}).get('cell_size'),
                       'regions': list((recipe.get('regions') or {}).keys()),
                       'cells': sorted(cells.values(), key=lambda c: (c['at'][1], c['at'][0])),
                       'touched_by': other, 'report': report and {k: v for k, v in report.items() if k != 'cells'},
                       'source': owner['key'] if owner else 'main'})
    worlds.sort(key=lambda w: (-len(w['touched_by']), w['path']))
    return worlds


def history(cfg, key, snap):
    """A card's history: its status log, and its own commits."""
    card = next((c for c in snap['agents'] if c['key'] == key), None)
    if card is None:
        return None
    events = []
    if card.get('id'):
        store = st.Store(snap['work_dir'])
        for e in store.history(card['id']):
            events.append({'t': e.get('t'), 'source': 'status', **{k: v for k, v in e.items() if k != 't'}})
    for c in card['git']['commits']:
        events.append({'t': c['t'], 'source': 'git', 'op': 'commit', 'text': c['subject'], 'sha': c['sha']})
    if card.get('started'):
        events.append({'t': card['started'], 'source': 'worktree', 'op': 'started'})
    events.sort(key=lambda e: -(e.get('t') or 0))
    return events


def resolve_image(snap, wt_key, relpath):
    """The file for /img?w=KEY&p=PATH: an image inside a worktree on the board, or None."""
    card = next((c for c in snap['agents'] if c['key'] == wt_key), None)
    if not card or not card.get('worktree') or not relpath:
        return None
    root = Path(card['worktree']).resolve()
    try:
        p = (root / relpath).resolve()
        p.relative_to(root)
    except (ValueError, OSError):
        return None
    if p.suffix.lower() not in IMAGE_TYPES or not p.is_file():
        return None
    return p
