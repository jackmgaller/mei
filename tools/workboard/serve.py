#!/usr/bin/env python3
"""The workboard: a local web page showing the agents working on Mei (README.md beside this).

    python3 tools/workboard/serve.py --port 8770      # then open http://127.0.0.1:8770/

It reads the status records (tools/work_status.py) and infers the rest from git and the kits'
outputs in each worktree, every --refresh seconds in the background. Read-only, except the
page's answer box, which records an answer to an agent's question in its status record.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workboard import infer, status as st  # noqa: E402

STATIC = Path(__file__).resolve().parent / 'static'
STATIC_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml'}


class Board:
    def __init__(self, cfg, refresh):
        self.cfg = cfg
        self.refresh = refresh
        self.cache = infer.Cache()
        self.snap = None
        self.body = b'{}'
        self.error = None
        self.lock = threading.Lock()
        self.wake = threading.Event()

    def update(self):
        try:
            snap = infer.snapshot(self.cfg, self.cache)
            body = json.dumps(snap, separators=(',', ':')).encode()
            with self.lock:
                self.snap, self.body, self.error = snap, body, None
        except Exception as e:  # keep serving the last good board
            traceback.print_exc()
            with self.lock:
                self.error = f'{type(e).__name__}: {e}'

    def loop(self):
        while True:
            self.wake.wait(self.refresh)
            self.wake.clear()
            self.update()


def make_handler(board):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'MeiWorkboard/1'

        def log_message(self, fmt, *args):
            if os.environ.get('WORKBOARD_LOG'):
                super().log_message(fmt, *args)

        def send(self, code, body, ctype='application/json', cache='no-store'):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def fail(self, code, msg):
            self.send(code, json.dumps({'error': msg}).encode())

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ('/', '/index.html'):
                return self.static('index.html')
            if u.path == '/favicon.ico':
                return self.send(204, b'', 'image/x-icon')
            if u.path.startswith('/static/'):
                return self.static(u.path[len('/static/'):])
            if u.path == '/api/state':
                with board.lock:
                    body, err = board.body, board.error
                if err:
                    snap = json.loads(body)
                    snap['error'] = err
                    body = json.dumps(snap).encode()
                return self.send(200, body)
            if u.path == '/api/history':
                with board.lock:
                    snap = board.snap
                ev = infer.history(board.cfg, q.get('key', [''])[0], snap) if snap else None
                if ev is None:
                    return self.fail(404, 'no such card')
                return self.send(200, json.dumps(ev).encode())
            if u.path == '/img':
                with board.lock:
                    snap = board.snap
                p = infer.resolve_image(snap, q.get('w', [''])[0], q.get('p', [''])[0]) if snap else None
                if p is None:
                    return self.fail(404, 'no such image')
                return self.send(200, p.read_bytes(), infer.IMAGE_TYPES[p.suffix.lower()], 'max-age=5')
            return self.fail(404, 'not found')

        def static(self, name):
            p = (STATIC / name).resolve()
            if p.parent != STATIC or p.suffix not in STATIC_TYPES or not p.is_file():
                return self.fail(404, 'not found')
            return self.send(200, p.read_bytes(), STATIC_TYPES[p.suffix])

        def do_POST(self):
            u = urlparse(self.path)
            origin = self.headers.get('Origin')
            host = self.headers.get('Host', '')
            if origin and urlparse(origin).netloc != host:
                return self.fail(403, 'cross-origin request')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.fail(415, 'JSON only')
            try:
                n = int(self.headers.get('Content-Length') or 0)
                data = json.loads(self.rfile.read(min(n, 65536)) or b'{}')
            except ValueError:
                return self.fail(400, 'bad JSON')
            if u.path == '/api/refresh':
                board.wake.set()
                return self.send(200, b'{"ok":true}')
            if u.path == '/api/answer':
                agent_id, qn, text = data.get('id'), data.get('n'), str(data.get('text') or '').strip()
                if not text or not isinstance(qn, int):
                    return self.fail(400, 'id, n and text are needed')
                try:
                    store = st.Store(board.snap['work_dir'])

                    def change(rec):
                        q = next((q for q in rec.get('questions') or [] if q.get('n') == qn), None)
                        if q is None:
                            raise st.StatusError(f'no question {qn}')
                        q['answer'], q['answered'] = text, st.now()
                    store.update(agent_id, change, 'answer', log={'n': qn, 'text': text, 'via': 'workboard'})
                except (st.StatusError, TypeError) as e:
                    return self.fail(400, str(e))
                board.wake.set()
                return self.send(200, b'{"ok":true}')
            return self.fail(404, 'not found')

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--repo', default=None, help='any checkout of the repository (default: this one)')
    ap.add_argument('--port', type=int, default=8770)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--base', default='main', help='the branch merged work lands on (default main)')
    ap.add_argument('--refresh', type=float, default=10, help='seconds between scans (default 10)')
    ap.add_argument('--stale', type=float, default=20, help='minutes without activity before a card is stale')
    ap.add_argument('--since', type=float, default=12,
                    help='hours: show worktrees active this recently, running, or with a status record')
    ap.add_argument('--branches', action='append', default=[], metavar='GLOB',
                    help='only these branches (repeatable, e.g. "shrinetown-*"); records always show')
    ap.add_argument('--all', action='store_true', help='every worktree, however old')
    ap.add_argument('--include-main', action='store_true', help='show the main checkout as a card')
    ap.add_argument('--once', action='store_true', help='print the board as JSON and exit')
    a = ap.parse_args(argv)

    repo = Path(a.repo or Path(__file__).resolve().parents[2]).resolve()
    work = os.environ.get('MEI_WORK_DIR')
    cfg = infer.Config(repo=repo, work_dir=Path(work).expanduser().resolve() if work else None, base=a.base,
                       stale_minutes=a.stale, since_hours=a.since, branches=a.branches,
                       include_main=a.include_main, show_all=a.all)
    if a.once:
        print(json.dumps(infer.snapshot(cfg), indent=1))
        return 0
    board = Board(cfg, a.refresh)
    t = time.time()
    board.update()
    snap = board.snap or {}
    print(f"workboard: {len(snap.get('agents', []))} agents of {snap.get('worktrees_total', 0)} worktrees "
          f"in {time.time() - t:.1f}s; status records in {snap.get('work_dir')}", flush=True)
    threading.Thread(target=board.loop, daemon=True).start()
    ThreadingHTTPServer.request_queue_size = 128   # a gallery asks for many thumbnails at once
    httpd = ThreadingHTTPServer((a.host, a.port), make_handler(board))
    print(f'workboard: http://{a.host}:{a.port}/', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
