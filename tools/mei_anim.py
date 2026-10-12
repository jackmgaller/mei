#!/usr/bin/env python3
"""Mei Animation Kit: keyframed moves for rigid-part rigs, checked, previewed by Mei and exported
for the cart's runtime (carts/mechexpo/anim.akr). docs/ANIMKIT.md has the format and the
commands.

  verify MOVE...            check the format, the timing, the boxes, the parts passing through
                            each other and the floor, frame by frame
  preview MOVE -o DIR       every frame drawn by Mei with its boxes, and a contact sheet
  export [-o DIR]           every move of every mech baked into anim_data.akr (+ anims/anim_data.bin)
  info MOVE                 the move's keys, boxes, marks and phases, frame by frame

verify and preview print a summary (--json: the full report); export prints its report.
"""
import json
from pathlib import Path
import sys

from kitcore import jsonio
from kitcore.cli import parser_class
from animkit.rig import AnimError
from animkit import summary

ROOT = Path(__file__).resolve().parents[1]
CART = ROOT/'carts'/'mechexpo'


def tool_paths(args):
    """meic and mei-headless: --compiler/--runner, else --build-dir, else $MEIC/$RUN, else $B, else
    build/ (kitcore.native.tool_paths())."""
    from kitcore.native import tool_paths as paths
    keys = ('compiler', 'runner')
    found = paths(keys, {k: getattr(args, k, None) or None for k in keys}, getattr(args, 'build_dir', None) or None)
    return {k: path for k, (path, _) in found.items()}


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
    for cmd in (pv,):
        cmd.add_argument('--build-dir', help='The Mei build directory (make B=DIR) with meic and mei-headless.')
        cmd.add_argument('--compiler')
        cmd.add_argument('--runner')
    return p


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
        if args is not None and not getattr(args, 'json', False) and args.command in ('verify', 'preview', 'info'):
            print(f'error at {path}: {error}')
        else:
            jsonio.output({'ok': False, 'errors': [{'path': path, 'message': str(error)}]})
        return 1


if __name__ == '__main__':
    sys.exit(main())
