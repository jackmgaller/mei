#!/usr/bin/env python3
"""Mei Animation Kit: keyframed moves for rigid-part rigs, checked, previewed by Mei and exported
for the cart's runtime (carts/mechexpo/anim.akr). docs/ANIMKIT.md has the format and the
commands.

  verify MOVE...            check the format, the timing, the boxes, the parts passing through
                            each other and the floor, frame by frame
  preview MOVE -o DIR       every frame drawn by Mei with its boxes, and a contact sheet
  export [-o DIR]           every move of every mech baked into anim_data.akr (+ anims/anim_data.bin)
  info MOVE                 the move's keys, boxes, marks and phases, frame by frame
  pose MOVE                 where each frame puts things: joints, blades (base, tip, aim),
                            boxes, the lowest point of each part, the top of the hurt boxes
  fmt [MOVE...]             rewrite move files in the one compact style (default: the cart's)
  check                     fmt --check, verify every move, export, and run the kit's two suites

verify, preview, pose and info print a summary (--json: the full report); export prints its report.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from kitcore import jsonio
from kitcore.cli import parser_class
from animkit.rig import AnimError
from animkit import summary

ROOT = Path(__file__).resolve().parents[1]
CART = ROOT/'carts'/'mechexpo'
TESTS = CART/'tests'/'anim'


def all_moves():
    """Every move file check verifies: the cart's, the test cart's and the examples."""
    return (sorted(p for p in (CART/'anims').glob('*/*.anim.json') if not p.name.startswith('_')) +
            sorted((TESTS/'anims').glob('*/*.anim.json')) + sorted((TESTS/'examples').glob('*.anim.json')))


def tool_paths(args):
    """meic and mei-headless: --compiler/--runner, else --build-dir, else $MEIC/$RUN, else $B, else build/."""
    out = {}
    for key, variable, executable in (('compiler', 'MEIC', 'meic'), ('runner', 'RUN', 'mei-headless')):
        given = getattr(args, key, None)
        if given:
            out[key] = Path(given)
        elif getattr(args, 'build_dir', None):
            out[key] = Path(args.build_dir)/executable
        elif os.environ.get(variable):
            out[key] = Path(os.environ[variable])
        elif os.environ.get('B'):
            out[key] = ROOT/os.environ['B']/executable
        else:
            out[key] = ROOT/'build'/executable
        out[key] = out[key].resolve()
    return out


def parser():
    p = parser_class(AnimError)(description=__doc__, formatter_class=__import__('argparse').RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('verify', help='Check moves: format, timing, boxes, parts passing through each other, the floor.')
    v.add_argument('moves', nargs='+', help='MOVE.anim.json files.')
    v.add_argument('--json', action='store_true', help='The full report as JSON.')
    v.add_argument('--tolerance', type=float, default=0.12,
                   help='How much deeper (m) two parts may pass into each other than the rig\'s own poses have them (default 0.12).')
    pv = sub.add_parser('preview', help='Draw every frame with Mei, boxes on, and a contact sheet.')
    pv.add_argument('move', help='MOVE.anim.json.')
    pv.add_argument('-o', '--output', required=True, help='The output directory (in your build directory).')
    pv.add_argument('--as', dest='as_move', help='Preview it in this move\'s place (a file not named after a move).')
    pv.add_argument('--every', type=int, help='Put every Nth frame on the sheet (default: about 24 frames), and every key.')
    pv.add_argument('--columns', type=int, default=6)
    pv.add_argument('--distance', type=float, default=15.0, help='The camera\'s distance (m); the game\'s is about 31.')
    pv.add_argument('--no-boxes', action='store_true')
    pv.add_argument('--json', action='store_true')
    ex = sub.add_parser('export', help='Bake every move of every mech for the runtime.')
    ex.add_argument('-o', '--output', default=str(CART), help='Where anim_data.akr and anims/anim_data.bin go (default the cart).')
    ex.add_argument('--anims', default=str(CART/'anims'), help='The moves\' folder, MECH/MOVE.anim.json (default the cart\'s).')
    ex.add_argument('--extra', action='append', default=[], metavar='DIR',
                    help='More moves, DIR/MECH/MOVE.anim.json, in place of the cart\'s (a test\'s moves). Repeatable.')
    ex.add_argument('--runtime', action='store_true', help='Also copy the cart\'s anim.akr into the output (for a test or '
                    'preview cart that imports it from there).')
    ex.add_argument('--no-meshes', action='store_true', help='Reference no meshes (no pack import): placeholder data.')
    inf = sub.add_parser('info', help='The move frame by frame: keys, boxes, marks, motion.')
    inf.add_argument('move')
    inf.add_argument('--json', action='store_true')
    inf.add_argument('--joints', action='store_true', help='Where each frame puts things (as pose).')
    inf.add_argument('--frames', help='With --joints: as pose\'s.')
    po = sub.add_parser('pose', help='Where each frame puts the joints, the blades, the boxes and the lowest points.')
    po.add_argument('move')
    po.add_argument('--frames', help='Which frames: "13", "10-16,20", "keys" (default every frame).')
    po.add_argument('--no-joints', action='store_true', help='Leave the joints out of the summary.')
    po.add_argument('--json', action='store_true')
    fm = sub.add_parser('fmt', help='Rewrite move files in the one compact style.')
    fm.add_argument('moves', nargs='*', help='MOVE.anim.json files (default: every file of the cart\'s anims/).')
    fm.add_argument('--check', action='store_true', help='Only list the files that would change; exit 1 if any.')
    ck = sub.add_parser('check', help='fmt --check, verify every move, export into the cart, run the kit\'s suites.')
    ck.add_argument('--no-tests', action='store_true', help='Stop after the export.')
    ck.add_argument('--fight', action='store_true', help='Also run the cart\'s fight scenarios (tests/check.sh).')
    ck.add_argument('--tolerance', type=float, default=0.12)
    for cmd in (pv, ck):
        cmd.add_argument('--build-dir', help='The Mei build directory (make B=DIR) with meic and mei-headless.')
        cmd.add_argument('--compiler')
        cmd.add_argument('--runner')
    return p


def check(args):
    """The animator's one command before committing: every step prints a line; stops at the first
    failure (exit 1)."""
    from animkit.fmt import fmt
    from animkit.verify import verify
    from animkit.export import export
    files = sorted((CART/'anims').glob('*/*.anim.json'))
    unformatted = fmt(files, check=True)
    if unformatted:
        print('FAILED fmt: not in the compact style (run `mei_anim.py fmt`):\n  ' + '\n  '.join(unformatted))
        return 1
    print(f'fmt: {len(files)} files in the style')
    moves = all_moves()
    reports = [verify(m, args.tolerance) for m in moves]
    bad = [r for r in reports if not r['ok']]
    warned = sum(len(r['warnings']) for r in reports)
    if bad:
        print('\n\n'.join(summary.verify_text(r) for r in bad))
        print(f'FAILED verify: {len(bad)} of {len(moves)} moves')
        return 1
    print(f'verify: {len(moves)} moves pass ({warned} warnings: `mei_anim.py verify MOVE` lists them)')
    data = [CART/'anim_data.akr', CART/'anims'/'anim_data.bin']
    before = [p.read_bytes() if p.is_file() else None for p in data]
    report = export(CART/'anims', CART, CART)
    after = [p.read_bytes() for p in data]
    print(f'export: {len(report["moves"])} moves, {report["bytes"]:,} bytes; anim_data ' +
          ('unchanged' if before == after else 'changed (commit it with the moves)'))
    if args.no_tests:
        return 0
    tools = tool_paths(args)
    env = dict(os.environ, MEIC=str(tools['compiler']), RUN=str(tools['runner']), PYTHONDONTWRITEBYTECODE='1')
    if 'B' not in env:
        env['B'] = os.path.relpath(tools['compiler'].parent, ROOT)
    steps = [('tests/test_animkit.py', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p',
                                        'test_animkit.py']),
             ('tests/anim/check.sh', [str(TESTS/'check.sh')])]
    if args.fight:
        steps.append(('tests/check.sh', [str(CART/'tests'/'check.sh')]))
    for name, cmd in steps:
        run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        if run.returncode:
            print((run.stdout+run.stderr)[-3000:])
            print(f'FAILED {name}')
            return 1
        last = [l for l in (run.stdout+run.stderr).splitlines() if l.strip()]
        print(f'{name}: ' + (last[-1] if last else 'ok'))
    print('all checks passed')
    return 0


def main(argv=None):
    args = None
    try:
        args = parser().parse_args(argv)
        if args.command == 'verify':
            from animkit.verify import verify
            reports = [verify(m, args.tolerance) for m in args.moves]
            ok = all(r['ok'] for r in reports)
            if args.json:
                jsonio.output(reports[0] if len(reports) == 1 else {'ok': ok, 'moves': reports})
            else:
                print('\n\n'.join(summary.verify_text(r) for r in reports))
            return 0 if ok else 1
        if args.command == 'preview':
            from animkit.preview import preview
            tools = tool_paths(args)
            report = preview(args.move, args.output, tools['compiler'], tools['runner'], args.as_move, args.every,
                             args.columns, not args.no_boxes, args.distance)
            if args.json:
                jsonio.output(report)
            else:
                print(summary.preview_text(report))
            return 0
        if args.command == 'export':
            from animkit.export import export, find_moves
            import shutil
            over = {}
            for extra in args.extra:
                found, _ = find_moves(extra)
                over.update(found)
            report = export(args.anims, CART, args.output, not args.no_meshes, override=over)
            if args.runtime:
                shutil.copy(CART/'anim.akr', Path(args.output)/'anim.akr')
            jsonio.output({k: v for k, v in report.items() if k != 'moves'} |
                          {'moves': [f'{m["mech"]}/{m["move"]}: {m["length"]} frames' + (' (stand-in)' if m['stand_in'] else '')
                                     for m in report['moves']]})
            return 0
        if args.command == 'pose' or (args.command == 'info' and args.joints):
            from animkit.move import Move
            from animkit import pose
            move = Move(args.move)
            report = pose.report(move, pose.frames_arg(args.frames, move.length, [k[0] for k in move.pose_keys]))
            if args.json:
                jsonio.output(report)
            else:
                print(pose.text(report, not getattr(args, 'no_joints', False)))
            return 0
        if args.command == 'fmt':
            from animkit.fmt import fmt
            paths = args.moves or sorted((CART/'anims').glob('*/*.anim.json'))
            changed = fmt(paths, args.check)
            for c in changed:
                print(('would change: ' if args.check else 'formatted: ')+c)
            if not changed:
                print(f'{len(paths)} files already in the style')
            return 1 if args.check and changed else 0
        if args.command == 'check':
            return check(args)
        if args.command == 'info':
            from animkit.move import Move
            move = Move(args.move)
            report = summary.info(move)
            if args.json:
                jsonio.output(report)
            else:
                print(summary.info_text(report))
            return 0
    except (AnimError, OSError, ValueError) as error:
        path = getattr(error, 'path', '/input')
        if args is not None and not getattr(args, 'json', False) and args.command in ('verify', 'preview', 'info',
                                                                                    'pose', 'fmt', 'check'):
            print(f'error at {path}: {error}')
        else:
            jsonio.output({'ok': False, 'errors': [{'path': path, 'message': str(error)}]})
        return 1


if __name__ == '__main__':
    sys.exit(main())
