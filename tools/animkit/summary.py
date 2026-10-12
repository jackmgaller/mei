"""The plain-text summaries verify, preview and info print (--json gives the full reports)."""
from .move import MARKS, KINDS


def verify_text(r):
    head = f'{r.get("name", r["move"])}: ' + ('PASS' if r['ok'] else f'FAIL ({r["verdict"]})')
    lines = [head, f'  file: {r["move"]}']
    if 'length' in r:
        ph = r.get('phases')
        lines.append(f'  {r["length"]} frames, keys at {", ".join(str(k) for k in r["keys"])}'
                     + (f'; startup {ph["startup"]}, active {ph["active"]}, recovery {ph["recovery"]}' if ph else ''))
        ch = r.get('checks', {})
        if ch:
            ext = ch.get('hit_extent')
            if ext:
                lines.append(f'  hit boxes span x {ext[0]:.2f} to {ext[2]:.2f}, y {ext[1]:.2f} to {ext[3]:.2f}')
            lines.append(f'  active frames {ch.get("active_frames")}; lowest point {ch.get("lowest", 0):+.3f} m; '
                         f'{ch.get("part_pairs", 0)} piece pairs checked; up to {ch.get("boxes", {}).get("per_frame_max", 0)} boxes a frame')
    for f in r['failures']:
        lines.append(f'  FAIL {f["check"]}: ' + (f'at {f["path"]}: ' if f.get('path') else '') + f['message'])
    for w in r['warnings']:
        lines.append(f'  warn {w["check"]}: ' + (f'at {w["path"]}: ' if w.get('path') else '') + w['message'])
    return '\n'.join(lines)


def preview_text(r):
    c = r['cost']
    lines = [f'{r["move"]}: {r["length"]} frames drawn by Mei, keys at {", ".join(str(k) for k in r["keys"])}',
             f'  contact sheet: {r["contact"]} (frames {", ".join(str(f) for f in r["sheet_frames"])})',
             f'  every frame: {r["frames"]}/frame_NNN.png',
             f'  frame cost, the worst: CPU {c["cpu_max"]:,} of {c["budget"]["cpu"]:,} cycles, '
             f'GPU {c["gpu_max"]:,} of {c["budget"]["gpu"]:,} (one mech, the preview\'s camera)']
    for w in r.get('warnings', []):
        lines.append(f'  warn: at {w["path"]}: {w["message"]}')
    return '\n'.join(lines)


def info(move):
    frames = []
    for f in range(move.length):
        mats = move.matrices(f)
        boxes = move.boxes_at(f, mats)
        frames.append({'frame': f, 'marks': [k for k, b in MARKS.items() if move.marks[f] & b],
                       'boxes': [{'name': n, 'kind': k, 'hit': h, 'part': p, 'rect': [x0, y0, x1, y1]}
                                 for n, k, h, p, x0, y0, x1, y1 in boxes]})
    motion = move.motion_raw()
    for f, (dx, dy) in enumerate(motion):
        frames[f]['root'] = [dx/65536, dy/65536]
    return {'name': move.name, 'rig': move.rig.name, 'length': move.length, 'loop': move.loop, 'air': move.air,
            'keys': [{'at': k[0], 'ease': k[1]} for k in move.pose_keys], 'phases': move.phases, 'frames': frames}


def info_text(r):
    lines = [f'{r["name"]} ({r["rig"]}): {r["length"]} frames' + (', loops' if r['loop'] else '') +
             (', airborne' if r['air'] else ''),
             '  keys: ' + ', '.join(f'{k["at"]} ({k["ease"]})' for k in r['keys'])]
    prev = None
    for fr in r['frames']:
        hits = [b for b in fr['boxes'] if b['kind'] == 'hit']
        desc = (f'hit {" ".join(b["name"] for b in hits)}' if hits else '') + \
               (f' marks {",".join(fr["marks"])}' if fr['marks'] else '') + \
               (f' root {fr["root"][0]:+.3f},{fr["root"][1]:+.3f}' if any(fr.get('root', [0, 0])) else '')
        if desc != prev:
            lines.append(f'  {fr["frame"]:3d}: {len(fr["boxes"])} boxes ' + desc)
            prev = desc
    return '\n'.join(lines)
