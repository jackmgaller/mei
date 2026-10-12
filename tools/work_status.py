#!/usr/bin/env python3
"""Report an agent's status to the workboard (tools/workboard/README.md).

    python3 tools/work_status.py new ID --title "..." --kind asset --model sonnet --branch B
    python3 tools/work_status.py set ID --state working --step "LOD pass" --percent 60
    python3 tools/work_status.py item ID NAME --state done --size small
    python3 tools/work_status.py ask ID "Which roof colour for the shrine office?"
    python3 tools/work_status.py done ID          (also: review, merged, stop, block ID "why")

Records live in $MEI_WORK_DIR, else <git common dir>/mei-work, shared by every worktree and
never committed. Run inside a worktree, the branch and worktree are filled in when missing.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workboard import status as st  # noqa: E402


def here():
    """(branch, worktree) of the current directory, or (None, None) in the main checkout."""
    top = st.git_out(os.getcwd(), 'rev-parse', '--show-toplevel')
    git_dir = st.git_out(os.getcwd(), 'rev-parse', '--absolute-git-dir')
    common = st.git_out(os.getcwd(), 'rev-parse', '--git-common-dir')
    if not top or not git_dir or not common:
        return None, None
    common = Path(common) if Path(common).is_absolute() else Path(os.getcwd()) / common
    if Path(git_dir).resolve() == common.resolve():
        return None, None
    branch = st.git_out(os.getcwd(), 'rev-parse', '--abbrev-ref', 'HEAD')
    return (branch if branch and branch != 'HEAD' else None), str(Path(top).resolve())


def fill_here(rec):
    branch, worktree = here()
    if worktree and not rec.get('worktree') and (not rec.get('branch') or rec['branch'] == branch):
        rec['worktree'] = worktree
    if branch and not rec.get('branch') and rec.get('worktree') == worktree:
        rec['branch'] = branch


def percent(v):
    v = int(v)
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError('percent is 0 to 100')
    return v


def add_fields(p, defaults=False):
    p.add_argument('--title')
    p.add_argument('--kind', choices=st.KINDS)
    p.add_argument('--model', help='opus, sonnet, haiku, ...')
    p.add_argument('--lead', help='the id of the agent that started this one')
    p.add_argument('--branch')
    p.add_argument('--worktree')
    p.add_argument('--state', choices=st.STATES)
    p.add_argument('--step', help='one line: what is happening now')
    p.add_argument('--percent', type=percent)
    p.add_argument('--note', help='a free note, appended to the notes')


def apply_fields(rec, a):
    for k in ('title', 'kind', 'model', 'lead', 'branch', 'step', 'percent'):
        v = getattr(a, k, None)
        if v is not None:
            rec[k] = v
    if getattr(a, 'worktree', None):
        rec['worktree'] = str(Path(a.worktree).expanduser().resolve())
    if getattr(a, 'state', None):
        st.set_state(rec, a.state)
    if getattr(a, 'note', None):
        rec.setdefault('notes', []).append({'t': st.now(), 'text': a.note})


def given(a, keys):
    return {k: getattr(a, k) for k in keys if getattr(a, k, None) is not None}


FIELD_KEYS = ('title', 'kind', 'model', 'lead', 'branch', 'worktree', 'state', 'step', 'percent', 'note')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('new', help='create or reset an agent record (the orchestrator)')
    p.add_argument('id')
    add_fields(p)
    p = sub.add_parser('set', help='change fields')
    p.add_argument('id')
    add_fields(p)
    p = sub.add_parser('item', help='add or change one item (an asset, a cell, ...)')
    p.add_argument('id')
    p.add_argument('name')
    p.add_argument('--state', choices=st.ITEM_STATES)
    p.add_argument('--size', choices=st.SIZES)
    p.add_argument('--note')
    p = sub.add_parser('ask', help='ask the owner a question')
    p.add_argument('id')
    p.add_argument('text')
    p = sub.add_parser('answer', help='answer question N (the owner or the lead)')
    p.add_argument('id')
    p.add_argument('n', type=int)
    p.add_argument('text')
    p = sub.add_parser('note', help='append a free note')
    p.add_argument('id')
    p.add_argument('text')
    for name, state in (('done', 'done'), ('review', 'review'), ('merged', 'merged'), ('stop', 'stopped')):
        p = sub.add_parser(name, help=f'set the state to {state}')
        p.add_argument('id')
        p.add_argument('--note')
        p.set_defaults(final_state=state)
    p = sub.add_parser('block', help='set the state to blocked, with the reason as the step')
    p.add_argument('id')
    p.add_argument('reason')
    p = sub.add_parser('show', help='print a record (JSON), with its open questions and answers')
    p.add_argument('id')
    sub.add_parser('list', help='one line per agent')
    sub.add_parser('path', help='print the status folder')

    a = ap.parse_args(argv)
    try:
        store = st.Store(st.work_dir())
        if a.cmd == 'path':
            print(store.root)
            return 0
        if a.cmd == 'list':
            for r in store.all():
                age = int((time.time() - (r.get('updated') or 0)) / 60)
                print(f"{r['id']:<28} {r.get('state') or '':<8} {r.get('model') or '-':<7} "
                      f"{r.get('kind') or '':<6} {age:>4}m  {r.get('step') or ''}")
            return 0
        if a.cmd == 'show':
            rec = store.read(st.check_id(a.id))
            if rec is None:
                raise st.StatusError(f'no status for {a.id!r}')
            print(json.dumps(rec, indent=1))
            return 0

        if a.cmd == 'new':
            def change(rec):
                if not a.branch and not a.worktree:
                    fill_here(rec)
                apply_fields(rec, a)
                if rec['state'] == 'working' and not rec.get('started'):
                    rec['started'] = st.now()
            rec = store.update(a.id, change, 'new', create=True, log=given(a, FIELD_KEYS))
        elif a.cmd == 'set':
            def change(rec):
                apply_fields(rec, a)
                fill_here(rec)
            rec = store.update(a.id, change, 'set', log=given(a, FIELD_KEYS))
        elif a.cmd == 'item':
            def change(rec):
                st.set_item(rec, a.name, a.state, a.size, a.note)
                if rec.get('state') == 'queued' and a.state == 'working':
                    st.set_state(rec, 'working')
                fill_here(rec)
            rec = store.update(a.id, change, 'item', log={'name': a.name, **given(a, ('state', 'size', 'note'))})
        elif a.cmd == 'ask':
            def change(rec):
                qs = rec.setdefault('questions', [])
                qs.append({'n': len(qs) + 1, 'text': a.text, 'asked': st.now(), 'answer': None, 'answered': None})
                fill_here(rec)
            rec = store.update(a.id, change, 'ask', log={'text': a.text})
            print(f"question {len(rec['questions'])}")
            return 0
        elif a.cmd == 'answer':
            def change(rec):
                q = next((q for q in rec.get('questions') or [] if q.get('n') == a.n), None)
                if q is None:
                    raise st.StatusError(f'{a.id} has no question {a.n}')
                q['answer'], q['answered'] = a.text, st.now()
            rec = store.update(a.id, change, 'answer', log={'n': a.n, 'text': a.text})
        elif a.cmd == 'note':
            def change(rec):
                rec.setdefault('notes', []).append({'t': st.now(), 'text': a.text})
            rec = store.update(a.id, change, 'note', log={'text': a.text})
        elif a.cmd == 'block':
            def change(rec):
                st.set_state(rec, 'blocked')
                rec['step'] = a.reason
                fill_here(rec)
            rec = store.update(a.id, change, 'block', log={'reason': a.reason})
        else:
            def change(rec):
                st.set_state(rec, a.final_state)
                if a.note:
                    rec.setdefault('notes', []).append({'t': st.now(), 'text': a.note})
                fill_here(rec)
            rec = store.update(a.id, change, a.cmd, log=given(a, ('note',)))
        print(f"{rec['id']}: {rec['state']}" + (f" {rec['percent']}%" if rec.get('percent') is not None else '')
              + (f" - {rec['step']}" if rec.get('step') else ''))
        return 0
    except st.StatusError as e:
        print(f'work_status: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
