"""The workboard (tools/workboard/): the status helper tools/work_status.py, concurrent writers,
and what the board infers from git and the kits' outputs, in a temporary repository with
worktrees. Needs only git and the standard library. Run with
`python3 -m unittest discover -s tests -p test_workboard.py` (make test does).
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'tools/work_status.py'
sys.path.insert(0, str(ROOT / 'tools'))
from workboard import infer, status as st  # noqa: E402

GIT_ENV = {'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@example.com', 'GIT_COMMITTER_NAME': 't',
           'GIT_COMMITTER_EMAIL': 't@example.com', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.main = self.root / 'main'
        self.main.mkdir()
        git(self.main, 'init', '-q', '-b', 'main')
        write(self.main / 'README.md', 'x\n')
        write(self.main / '.gitignore', 'build-*/\n')
        write(self.main / 'w/town.world.json', {'format': 'mei-world', 'version': 1, 'name': 'town',
                                                'cell_dir': 'cells', 'grid': {'cell_size': 64}})
        for i in range(2):
            write(self.main / f'w/cells/c{i}.cell.json', {'format': 'mei-world-cell', 'version': 1,
                                                          'id': f'c{i}', 'at': [i, 0], 'placements': []})
        git(self.main, 'add', '-A')
        git(self.main, 'commit', '-q', '-m', 'start')
        self.work = self.root / 'work'
        self.env = {**os.environ, **GIT_ENV, 'MEI_WORK_DIR': str(self.work)}

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, cwd=None, ok=True):
        r = subprocess.run([sys.executable, str(CLI), *args], cwd=cwd or self.main, env=self.env,
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def worktree(self, name, branch):
        path = self.root / name
        git(self.main, 'worktree', 'add', '-q', '-b', branch, str(path))
        return path

    def snap(self, **kw):
        cfg = infer.Config(repo=self.main, work_dir=self.work, **kw)
        return infer.snapshot(cfg)


class TestStatusHelper(Repo):
    def test_lifecycle(self):
        self.cli('new', 'a1', '--title', 'Plaza props', '--kind', 'asset', '--model', 'sonnet',
                 '--branch', 'props', '--lead', 'boss')
        store = st.Store(self.work)
        rec = store.read('a1')
        self.assertEqual((rec['state'], rec['kind'], rec['model'], rec['branch']), ('queued', 'asset', 'sonnet', 'props'))
        self.assertIsNone(rec['worktree'], 'new in the main checkout does not claim it')
        self.cli('set', 'a1', '--state', 'working', '--step', 'LOD pass', '--percent', '60')
        self.cli('item', 'a1', 'bench', '--state', 'done', '--size', 'small')
        self.cli('item', 'a1', 'lamp', '--state', 'working')
        r = self.cli('ask', 'a1', 'Red or blue awning?')
        self.assertIn('question 1', r.stdout)
        self.cli('answer', 'a1', '1', 'Blue')
        rec = store.read('a1')
        self.assertEqual(rec['state'], 'working')
        self.assertEqual(rec['percent'], 60)
        self.assertIsNotNone(rec['started'])
        self.assertEqual([(i['name'], i['state'], i['size']) for i in rec['items']],
                         [('bench', 'done', 'small'), ('lamp', 'working', None)])
        self.assertEqual(rec['questions'][0]['answer'], 'Blue')
        self.assertEqual(st.item_percent(rec), 50)
        self.cli('done', 'a1', '--note', 'all three verified')
        rec = store.read('a1')
        self.assertEqual((rec['state'], rec['percent']), ('done', 100))
        self.assertIsNotNone(rec['ended'])
        ops = [e['op'] for e in store.history('a1')]
        self.assertEqual(ops, ['new', 'set', 'item', 'item', 'ask', 'answer', 'done'])

    def test_errors(self):
        r = self.cli('set', 'nobody', '--step', 'x', ok=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no status', r.stderr)
        r = self.cli('new', '../escape', ok=False)
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.root / 'escape.json').exists())
        r = self.cli('set', 'x', '--percent', '120', ok=False)
        self.assertNotEqual(r.returncode, 0)

    def test_fills_branch_and_worktree_from_a_worktree(self):
        wt = self.worktree('wt1', 'feature-x')
        self.cli('new', 'fx', '--kind', 'tool', cwd=wt)
        rec = st.Store(self.work).read('fx')
        self.assertEqual(rec['branch'], 'feature-x')
        self.assertEqual(rec['worktree'], str(wt))

    def test_default_folder_is_in_the_common_git_dir(self):
        wt = self.worktree('wt2', 'feature-y')
        env = {k: v for k, v in os.environ.items() if k != 'MEI_WORK_DIR'}
        self.assertEqual(st.work_dir(wt, env), (self.main / '.git/mei-work').resolve())
        self.assertEqual(st.work_dir(self.main, env), (self.main / '.git/mei-work').resolve())

    def test_concurrent_writers_lose_nothing(self):
        store = st.Store(self.work)
        store.update('c', lambda r: None, 'new', create=True)

        def worker(k):
            for i in range(25):
                store.update('c', lambda r, k=k, i=i: st.set_item(r, f'w{k}_{i}', 'done'), 'item')
        threads = [threading.Thread(target=worker, args=(k,)) for k in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(store.read('c')['items']), 150)
        self.assertEqual(len(store.history('c')), 151)
        self.assertEqual(list(store.status_dir.glob('.tmp-*')), [])


class TestInference(Repo):
    def test_board_from_git_and_build_outputs(self):
        wt = self.worktree('agent-a', 'town-props')
        # a committed recipe, an uncommitted cell edit and an Asset Kit report in a private build dir
        write(wt / 'w/assets/bench.asset.json', {'format': 'mei-asset', 'version': 1, 'name': 'bench',
                                                  'budget': {'triangles': 40}, 'nodes': []})
        git(wt, 'add', '-A')
        git(wt, 'commit', '-q', '-m', 'Town: a bench')
        write(wt / 'w/cells/c1.cell.json', {'format': 'mei-world-cell', 'version': 1, 'id': 'c1',
                                            'at': [1, 0], 'placements': [{'id': 'b'}]})
        out = wt / 'build-a/assets/bench'
        write(out / 'report.json', {'format': 'mei-asset-report', 'ok': True, 'name': 'bench', 'triangles': 34,
                                    'vertices': 32, 'budget': {'triangles': 40},
                                    'bounds': {'min': [-0.8, 0, -0.2], 'max': [0.8, 0.8, 0.2]},
                                    'verification': {'ok': True, 'verdict': 'PASS'}})
        (out / 'contact.png').write_bytes(b'\x89PNG\r\n\x1a\n')

        snap = self.snap(since_hours=1)
        keys = [c['key'] for c in snap['agents']]
        self.assertIn('agent-a', keys)
        card = next(c for c in snap['agents'] if c['key'] == 'agent-a')
        self.assertFalse(card['reported'])
        self.assertEqual(card['branch'], 'town-props')
        self.assertEqual(card['git']['commit_count'], 1)
        self.assertEqual(card['git']['commits'][0]['subject'], 'Town: a bench')
        self.assertEqual(card['git']['dirty_count'], 1)
        self.assertEqual(card['kind'], 'world')     # it touched a cell file
        self.assertEqual(card['state'], 'working')  # recent activity, uncommitted work
        assets = [a for a in snap['assets'] if a['card'] == 'agent-a']
        self.assertEqual(len(assets), 1)
        a = assets[0]
        self.assertEqual((a['name'], a['triangles'], a['budget'], a['verify'], a['state'], a['size']),
                         ('bench', 34, 40, 'pass', 'verified', 'small'))
        self.assertTrue(a['committed'])
        self.assertEqual(a['level'], 'w')
        self.assertEqual(a['recipe'], 'w/assets/bench.asset.json')
        img = a['images']['contact']
        self.assertTrue(img.startswith('/img?w=agent-a&p='))
        self.assertEqual(infer.resolve_image(snap, 'agent-a', 'build-a/assets/bench/contact.png'),
                         (out / 'contact.png').resolve())
        for bad in ('build-a/assets/bench/report.json', '../main/README.md', '/etc/passwd', ''):
            self.assertIsNone(infer.resolve_image(snap, 'agent-a', bad), bad)
        self.assertIsNone(infer.resolve_image(snap, 'nobody', 'build-a/assets/bench/contact.png'))

        world = next(w for w in snap['worlds'] if w['name'] == 'town')
        cells = {c['id']: c for c in world['cells']}
        self.assertEqual(cells['c0']['touched_by'], [])
        self.assertEqual([(t['card'], t['how']) for t in cells['c1']['touched_by']], [('agent-a', 'uncommitted')])

        # a status record joins the card by branch, and the reported state wins
        self.cli('new', 'props', '--branch', 'town-props', '--kind', 'asset', '--model', 'opus', '--state', 'review')
        self.cli('item', 'props', 'bench', '--size', 'medium')
        snap = self.snap(since_hours=1)
        card = next(c for c in snap['agents'] if c['key'] == 'agent-a')
        self.assertTrue(card['reported'])
        self.assertEqual((card['state'], card['model'], card['kind']), ('review', 'opus', 'asset'))
        a = next(a for a in snap['assets'] if a['card'] == 'agent-a')
        self.assertEqual(a['size'], 'medium')

    def test_stale_and_merged(self):
        wt = self.worktree('agent-c', 'quick-fix')
        write(wt / 'tools/fix.py', 'x = 1\n')
        git(wt, 'add', '-A')
        git(wt, 'commit', '-q', '-m', 'Fix a thing')
        self.cli('new', 'qf', '--branch', 'quick-fix', '--state', 'working')
        snap = self.snap(stale_minutes=20)
        card = next(c for c in snap['agents'] if c['key'] == 'agent-c')
        self.assertFalse(card['stale'])
        self.assertEqual(card['kind'], 'tool')
        snap = self.snap(stale_minutes=-1)       # everything is older than "now + 1 minute"
        card = next(c for c in snap['agents'] if c['key'] == 'agent-c')
        self.assertTrue(card['stale'])
        git(self.main, 'merge', '-q', '--ff-only', 'quick-fix')
        snap = self.snap()
        card = next(c for c in snap['agents'] if c['key'] == 'agent-c')
        self.assertEqual(card['inferred_state'], 'merged')
        self.assertEqual(card['state'], 'merged', 'a working record whose branch is merged shows as merged')

    def test_record_without_worktree_and_branch_filter(self):
        self.cli('new', 'later', '--title', 'Not started', '--kind', 'design')
        self.worktree('agent-d', 'other-thing')
        snap = self.snap(branches=['town-*'])
        keys = [c['key'] for c in snap['agents']]
        self.assertIn('later', keys)
        self.assertNotIn('agent-d', keys)
        q = self.cli('ask', 'later', 'Which palette?')
        self.assertIn('question 1', q.stdout)
        snap = self.snap()
        self.assertEqual([(x['card'], x['text']) for x in snap['questions']], [('later', 'Which palette?')])


if __name__ == '__main__':
    unittest.main()
