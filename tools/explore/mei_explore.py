#!/usr/bin/env python3
"""The explorer bot: where the robot can get to in a World Kit world, and what it should not get
to, confirmed by the real cart. See tools/explore/README.md.

    python3 tools/explore/mei_explore.py carts/garden/shrinetown/shrinetown.world.json --build-dir build-explore

Writes report.json, map.png, summary.txt and cases/*.akr into --out (default
BUILD/explore/WORLD/), and prints the summary.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from explore import confirm as C  # noqa: E402
from explore import finds as FD  # noqa: E402
from explore import moves as M  # noqa: E402
from explore import reach as R  # noqa: E402
from explore import report as REP  # noqa: E402
from explore import tuning as TN  # noqa: E402


def world_config(recipe, path=None):
    if path:
        return json.loads(Path(path).read_text())
    name = Path(recipe).name.split('.')[0]
    f = HERE / 'worlds' / f'{name}.json'
    return json.loads(f.read_text()) if f.exists() else {}


def commit():
    try:
        return subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True,
                              text=True).stdout.strip() or None
    except OSError:
        return None


def glide_items(cfg, frame):
    """Probes for the glide cases: the case's own take-off, the take-off moved along x and z,
    and aim errors."""
    g = cfg.get('glides')
    if not g:
        return []
    cases = C.glide_cases(ROOT / g['cases'])
    out = []
    offs = [(d, 0.0) for d in (-2, -1.5, -1, -0.5, 0.5, 1, 1.5, 2)] + [(0.0, d) for d in (-2, -1.5, -1, -0.5, 0.5, 1, 1.5, 2)]
    for name, gc in sorted(cases.items()):
        fx, _, fz = gc['from']
        tx, ty, tz = gc['to']
        base = dict(t=3300, mode=30, box=(tx, ty, tz), half=(gc['tol'], 0, 0), run=gc['run'])
        out.append((name, 'nominal', 0.0, 0.0, 0.0, C.Probe(find=f'glide-{name}', p=(fx, 90.0, fz), yaw=0, head=0.0, **base)))
        for dx, dz in offs:
            out.append((name, 'offset', dx, dz, 0.0, C.Probe(find=f'glide-{name}', p=(fx + dx, 90.0, fz + dz), yaw=0,
                                                             head=0.0, **base)))
        for a in (-20, -10, 10, 20):
            out.append((name, 'aim', 0.0, 0.0, a, C.Probe(find=f'glide-{name}', p=(fx, 90.0, fz), yaw=0,
                                                          head=math.radians(a), **base)))
    return out


def glide_windows(items, got):
    by = {}
    for (name, kind, dx, dz, aim, q), o in zip(items, got):
        tx, ty, tz = q.box
        ok = (o is not None and o.states >> C.ST_NAMES.index('glide') & 1 and
              math.hypot(o.land[0] - tx, o.land[2] - tz) < q.half[0] and o.land[1] >= ty - 0.01 and
              not (o.land == (0.0, 0.0, 0.0)))
        by.setdefault(name, []).append((kind, dx, dz, aim, bool(ok), o))
    out = []
    for name, rows in sorted(by.items()):
        nominal = [r for r in rows if r[0] == 'nominal']
        nom_ok = bool(nominal and nominal[0][4])

        def window(axis):
            good = {0.0: nom_ok}
            for kind, dx, dz, aim, ok, _ in rows:
                if kind == 'offset':
                    d = dx if axis == 'x' else dz
                    if (axis == 'x' and dz == 0) or (axis == 'z' and dx == 0):
                        good[float(d)] = ok
            if not nom_ok:
                return 0.0, sorted(d for d, v in good.items() if v)
            lo = hi = 0.0
            for d in sorted(k for k in good if k < 0)[::-1]:
                if good[d]:
                    lo = d
                else:
                    break
            for d in sorted(k for k in good if k > 0):
                if good[d]:
                    hi = d
                else:
                    break
            return hi - lo + 0.5, [lo, hi]
        wx, rx = window('x')
        wz, rz = window('z')
        aims = {f'{a:+d}': ok for kind, _, _, a, ok, _ in rows if kind == 'aim'}
        land = nominal[0][5].land if nominal and nominal[0][5] else None
        out.append({'name': name, 'nominal_ok': nom_ok, 'nominal_land': [round(v, 2) for v in land] if land else None,
                    'tried': len(rows), 'ok': sum(1 for r in rows if r[4]), 'window_x': wx, 'window_z': wz,
                    'range_x': rx, 'range_z': rz, 'aim_ok': aims,
                    'fails': [{'kind': k, 'dx': dx, 'dz': dz, 'aim': a,
                               'land': [round(v, 2) for v in o.land] if o else None, 'end_state': o.st if o else None}
                              for k, dx, dz, a, ok, o in rows if not ok][:24]})
    return out


def log(*a):
    print(*a, flush=True)


def leg_items(e, owner, node, pred=None, limit=40):
    """Probes for the flights of the cheapest route to node: each leg flown from its take-off,
    judged by whether the body gets within 1.5 m of where the reach map says it comes down."""
    from explore import finds as FD
    out = []
    pos = FD.node_positions(e)
    for k, (fs, row, v) in enumerate(e.route_flights(node, pred)[-limit:]):
        d = FD.describe_flight(e, fs, row)
        q = C.probe_for_flight(f'{owner["id"]}-leg{k + 1}', d, {'box': tuple(float(c) for c in pos[v]),
                                                                  'half': (1.5, 1.0, 1.5)})
        leg = {'id': f'{owner["id"]}-leg{k + 1}', 'takeoff': d, 'to': [round(float(c), 2) for c in pos[v]]}
        out.append(('leg', leg, q))
    return out


def legs_verdict(legs):
    """A route's legs flown headless: confirmed when every leg it can fly comes down where it
    should; the first that does not, and the legs it cannot fly (off a rail or a hang)."""
    flown = [g for g in legs if g.get('confirm')]
    not_flown = [g['id'] for g in legs if not g.get('confirm')]
    bad = [g for g in flown if not g['confirm'].get('confirmed')]
    return {'legs': len(legs), 'flown': len(flown), 'reproduced': len(flown) - len(bad),
            'first_failing': ({'id': bad[0]['id'], 'move': bad[0]['takeoff']['chain'], 'from': bad[0]['takeoff']['from'],
                               'expected': bad[0]['to'], 'got': bad[0]['confirm'].get('outcome', {}).get('end')}
                              if bad else None),
            'not_flown': not_flown, 'confirmed': bool(legs) and not bad and not not_flown}


def confirm_finds(e, finds, runner, a):
    """The headless confirmer over the finds: each find's own flight, and the legs of the route
    that reaches it. Returns the cases to write."""
    items = []
    routes = []                 # (owner dict, [leg dicts])

    def with_route(owner, node, pred=None):
        legs = leg_items(e, owner, node, pred)
        items.extend(legs)
        routes.append((owner, [g for _, g, _ in legs]))
    for f in finds['escapes'][:a.max_confirm]:
        items.append(('escape', f, C.probe_for_flight(f['id'], f['takeoff'])))
    for f in finds['escapes'][:min(a.max_confirm, 24)]:
        if f.get('_node') is not None:
            with_route(f, f['_node'])
    for f in finds['falls'][:min(a.max_confirm, 30)]:
        items.append(('fall_through', f, C.probe_for_flight(f['id'], f['takeoff'])))
    for s in finds['sealed']:
        b = s['box']
        box = ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
        half = ((b[3] - b[0]) / 2, (b[4] - b[1]) / 2, (b[5] - b[2]) / 2)
        for w in s['other_ways']:
            w['id'] = f'{s["id"]}-{w["move"]}'
            if w.get('flight'):
                q = C.probe_for_flight(w['id'], w['flight'], {'box': box, 'half': half})
                if q:
                    q.t = min(q.t + 600, 3000)
                items.append(('sealed', w, q))
            if w.get('_node') is not None:
                with_route(w, w['_node'])
    for c in finds['collectibles']:
        if c['type'] == 'star' and c.get('glide_take'):
            for w in c['ways']:
                if w.get('state') == 'glide' and w.get('takeoff'):
                    w['id'] = f'glide-take-{c["id"]}'
                    items.append(('glide_take', w, C.probe_for_flight(w['id'], w['takeoff'], {'pick': tuple(c['at'])})))
                    break
    for sc in finds['shortcuts']:
        if sc.get('bypassed') and sc.get('_end') is not None:
            sc['id'] = 'shortcut-' + sc['name'].split(',')[0]
            with_route(sc, sc['_end'], sc.get('_pred'))
    st = C.confirm(runner, items, tries=(6 if a.deep else a.tries), seed=a.seed)
    cases = []
    for (kind, f, q), s in zip(items, st):
        if q is None:
            continue
        f['confirm'] = s
        if s.get('confirmed') and kind != 'leg':
            f['title'] = f'{kind} {f.get("id", "")}'
            cases.append((kind, f, s))
    for owner, legs in routes:
        owner['route_check'] = legs_verdict(legs)
        owner['route_legs'] = [{'id': g['id'], 'chain': g['takeoff']['chain'], 'from': g['takeoff']['from'],
                                'to': g['to'], 'reproduced': g.get('confirm', {}).get('confirmed')} for g in legs]
    for c in finds['collectibles']:
        for w in c['ways']:
            if 'confirm' in w:
                c['glide_confirm'] = w['confirm']
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('recipe', help='the world recipe (WORLD.world.json)')
    ap.add_argument('--build-dir', default='build', help='the build directory: meic, mei-headless, the cart\'s worlds, '
                    'the kit cache (default build/)')
    ap.add_argument('--out', help='where to write the report (default BUILD/explore/WORLD)')
    ap.add_argument('--config', help='the world\'s explore notes (default tools/explore/worlds/WORLD.json)')
    ap.add_argument('--deep', action='store_true', help='the overnight mode: every half metre, more headings, deeper '
                    'kick chains, more tries and a denser drop check')
    ap.add_argument('--lattice', type=int, help='launch from every n-th column (0.25 m each); default 4, deep 2')
    ap.add_argument('--no-confirm', action='store_true', help='the reach map only')
    ap.add_argument('--tries', type=int, default=3, help='headless tries per find (seeded jitter after the first)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--processes', type=int, default=0)
    ap.add_argument('--max-confirm', type=int, default=60, help='finds of each kind to confirm')
    a = ap.parse_args(argv)
    t_all = time.perf_counter()
    build = Path(a.build_dir)
    if not build.is_absolute():
        build = (Path.cwd() / build).resolve()
    tn = TN.load()
    cfg = world_config(a.recipe, a.config)
    opts = R.Options(lattice=a.lattice or (2 if a.deep else 4), headings_extra=a.deep, kick_depth=3 if a.deep else 2,
                     processes=a.processes)
    log(f'explore {a.recipe}')
    t = time.perf_counter()
    e = R.Explorer(a.recipe, build, tn, cfg, opts=opts, log=log)
    e.run()
    finds = FD.all_finds(e, log=log)
    t_reach = time.perf_counter() - t
    name = e.world.meta['name']
    out = Path(a.out) if a.out else build / 'explore' / name
    out.mkdir(parents=True, exist_ok=True)
    for kind in ('escapes', 'falls', 'floorless', 'paths', 'traps'):
        for k, f in enumerate(finds[kind]):
            f['id'] = f'{kind[:-1] if kind.endswith("s") else kind}-{k + 1}'
    for s in finds['sealed']:
        s['id'] = 'sealed-' + s['name'].split(' ')[0]
    t = time.perf_counter()
    cases = []
    if not a.no_confirm and name in C.WORLD_CONST:
        ymin = float(e.m.floors.y.min()) - 5.0
        runner = C.Runner(build, name, e.m.frame, ymin=ymin, processes=a.processes, log=log)
        cases += confirm_finds(e, finds, runner, a)
        # the drop check: the real controller dropped over each floorless spot near a reachable floor
        pts, spacing = FD.drop_points(e, spacing=1.0 if a.deep else 1.5, limit=6000 if a.deep else 2500)
        dprobes = [C.Probe(find='drop', p=p, yaw=0, head=0, mode=C.MODE_DROP, t=240) for p in pts]
        got = runner.run(dprobes, name='drops') if dprobes else []
        byk = {o.k: o for o in got}
        drops = []
        for k, p in enumerate(pts):
            o = byk.get(k)
            drops.append({'at': [round(v, 2) for v in p], 'confirmed': bool(o and o.through >= 0),
                          'end': [round(v, 2) for v in o.end] if o else None})
        finds['drops'] = drops
        finds['drop_spacing_m'] = round(spacing, 2)
        finds['drop_clusters'] = FD.drop_clusters(e, drops)
        for k, c in enumerate(finds['drop_clusters']):
            c['id'] = f'drop-{k + 1}'
            p = c['points'][0]
            q = C.Probe(find=c['id'], p=tuple(p), yaw=0, head=0, mode=C.MODE_DROP, t=240, seed=a.seed)
            cases.append(('drop', c, {'probe': C.asdict(q), 'seed': a.seed, 'attempt': 0}))
        # the glide cases' take-off windows
        gi = glide_items(cfg, e.m.frame)
        if gi:
            got = runner.run([q for *_, q in gi], name='glides')
            byk = {o.k: o for o in got}
            finds['glides'] = glide_windows(gi, [byk.get(k) for k in range(len(gi))])
        confirm_info = {'ticks': runner.ticks, 'seconds': round(runner.seconds, 1)}
    else:
        confirm_info = None
    t_conf = time.perf_counter() - t
    # cases to paste
    cdir = out / 'cases'
    cdir.mkdir(exist_ok=True)
    for old in cdir.glob('*.akr'):
        old.unlink()
    written = []
    for kind, f, s in cases:
        fn = cdir / f'{f.get("id", kind)}.akr'
        fn.write_text(C.case_text(name, kind, f, s))
        written.append(str(fn))
    if cases:
        (cdir / 'explore_driver.akr').write_text(C.DRIVER_HEAD.split('const EX_WORLD')[0] + C.DRIVER)
    rep = {
        'format': 'mei-explore', 'version': 1, 'commit': commit(),
        'world': {'name': name, 'recipe': str(a.recipe), 'frame': list(e.m.frame), 'spawn': list(e.spawn) if e.spawn else None},
        'tuning': {'sources': tn.sources, 'reaches_m': tn.summary(), 'probe': tn.probe},
        'moves': [{'name': m.name, 'what': m.what} for m in M.MOVES],
        'options': {'lattice_m': opts.lattice * e.m.grid, 'headings_extra': opts.headings_extra,
                    'kick_depth': opts.kick_depth, 'deep': a.deep, 'tries': a.tries, 'seed': a.seed},
        'graph': {'floor_entries': int(e.n_floor), 'nodes': int(e.n_nodes),
                  'reachable_floor_entries': int(sum(1 for _ in [0]) and int((e.dist[:e.n_floor] < 1e30).sum())),
                  'flights': int(sum(len(b) for b in e.flights.batch))},
        'timing': {**e.timing, 'reach': round(t_reach, 1), 'confirm': round(t_conf, 1)},
        'confirm': confirm_info,
        'seconds': round(time.perf_counter() - t_all, 1),
        'finds': finds,
        'cases': written,
    }
    REP.draw_map(e, finds, None, out / 'map.png')
    rep['map'] = str(out / 'map.png')
    rep['seconds'] = round(time.perf_counter() - t_all, 1)
    text = REP.write(rep, out)
    print(text)
    print(f'wrote {out}/report.json, map.png, summary.txt and {len(written)} cases')
    return 0


if __name__ == '__main__':
    sys.exit(main())
