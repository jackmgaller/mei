"""`mei_anim.py pose`: where a move's poses put things, frame by frame: every joint, each weapon's
base and tip and the direction its blade points (the same [elevation, yaw] as a key's "aim"),
each box, the lowest point of each part and the top of the hurt boxes. Fight-local metres: x
forward, y up, from the root; "side" is the model's +X, the mech's left (away from the game's
camera)."""
import math

from .rig import apply


def blade_angles(m):
    """[elevation, yaw] in degrees of a part's +Y axis (a weapon's blade) posed by m."""
    ax = (m[0][1], m[1][1], m[2][1])
    n = math.sqrt(sum(v*v for v in ax)) or 1.0
    e = math.degrees(math.asin(max(-1.0, min(1.0, ax[1]/n))))
    y = math.degrees(math.atan2(ax[0], -ax[2])) if math.hypot(ax[0], ax[2]) > 1e-6 else 0.0
    return [round(e, 1), round(y, 1)]


def local(p):
    """A root-relative model point as fight-local [forward, up, side]."""
    return [round(-p[2], 3), round(p[1], 3), round(p[0], 3)]


def frame_report(move, f):
    rig = move.rig
    mats = move.matrices(f)
    rot, off = move.pose_at(f)
    prox = rig.proxies()
    joints = {j: local((mats[j][0][3], mats[j][1][3], mats[j][2][3])) for j in rig.order}
    weapons = {}
    for w in ('weapon_r', 'weapon_l'):
        if w not in prox:
            continue
        b = rig.bounds(w)
        m = mats[w]
        weapons[w] = {'base': joints[w], 'tip': local(apply(m, (0.0, b[1][1], 0.0))),
                      'aim': blade_angles(m)}
    lift = move.root_travel(f)[1]
    lowest = {}
    for pid, px in prox.items():
        m = mats[pid]
        lowest[pid] = round(lift+min(m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2]+m[1][3] for v in px['points']), 3)
    boxes = [{'name': n, 'kind': k, 'hit': h, 'part': p, 'rect': [x0, y0, x1, y1]}
             for n, k, h, p, x0, y0, x1, y1 in move.boxes_at(f, mats)]
    hurt = [b['rect'][3] for b in boxes if b['kind'] == 'hurt']
    return {'frame': f, 'key': any(k[0] == f for k in move.pose_keys),
            'offset': [round(v, 4) for v in off], 'root': [round(v, 4) for v in move.root_travel(f)],
            'rotate': {j: [round(v, 2) for v in r] for j, r in rot.items()},
            'joints': joints, 'weapons': weapons, 'boxes': boxes, 'lowest': lowest,
            'hurt_top': max(hurt) if hurt else None}


def frames_arg(text, length, keys):
    """'3,10-12' -> [3, 10, 11, 12]; 'keys' -> the key frames; None -> every frame."""
    if not text:
        return list(range(length))
    if text == 'keys':
        return sorted(set(keys))
    out = []
    for part in text.split(','):
        part = part.strip()
        if '-' in part[1:]:
            a, b = part.split('-', 1)
            out += range(int(a), int(b)+1)
        else:
            out.append(int(part))
    return [f for f in out if 0 <= f < length]


def report(move, frames=None):
    return {'name': move.name, 'rig': move.rig.name, 'length': move.length,
            'aims': [{'frame': a, 'part': p, 'wrist': w, 'rotate': r} for a, p, w, r in move.aims],
            'floor_keys': [{'frame': a, 'offset_up': u, 'lowest': who} for a, u, who in move.floor_report],
            'frames': [frame_report(move, f) for f in (frames if frames is not None else range(move.length))]}


def wrapped(label, items, width=100):
    """'  label  a  b  c' filled to width, continuation lines indented under the first item."""
    lines, cur = [], f'  {label:8s} '
    for it in items:
        if len(cur)+len(it)+2 > width and cur.strip() != label:
            lines.append(cur.rstrip())
            cur = ' '*11
        cur += it+'  '
    lines.append(cur.rstrip())
    return lines


def text(r, joints=True):
    xy = lambda p: f'{p[0]:.2f},{p[1]:.2f}'
    lines = [f'{r["name"]} ({r["rig"]}): {r["length"]} frames; points are forward,up from the root (m)']
    for a in r['aims']:
        lines.append(f'  aim on frame {a["frame"]}: {a["wrist"]} {a["rotate"]} points {a["part"]}')
    for k in r['floor_keys']:
        lines.append(f'  floor on frame {k["frame"]}: offset up {k["offset_up"]:.3f} ({k["lowest"]} on the floor)')
    for fr in r['frames']:
        lines.append(f'frame {fr["frame"]}' + (' KEY' if fr['key'] else '') +
                     f': offset {fr["offset"][0]:+.2f},{fr["offset"][1]:+.2f}' +
                     (f'; root moved {fr["root"][0]:+.2f},{fr["root"][1]:+.2f}' if any(fr['root']) else ''))
        if joints:
            lines += wrapped('joints', [f'{j} {xy(p)}' for j, p in fr['joints'].items()])
        for w, d in fr['weapons'].items():
            lines.append(f'  {w:8s} base {xy(d["base"])} side {d["base"][2]:+.2f}, tip {xy(d["tip"])} side '
                         f'{d["tip"][2]:+.2f}; aim [{d["aim"][0]:g}, {d["aim"][1]:g}]')
        for b in fr['boxes']:
            if b['kind'] != 'push':
                x0, y0, x1, y1 = b['rect']
                lines.append(f'  {b["kind"]:4s} {b["name"]:11s} x {x0:.2f} to {x1:.2f}, y {y0:.2f} to {y1:.2f}')
        low = sorted(fr['lowest'].items(), key=lambda kv: kv[1])
        lines += wrapped('lowest', [f'{p} {v:+.2f}' for p, v in low])
        if fr['hurt_top'] is not None:
            lines.append(f'  hurt top {fr["hurt_top"]:.2f}')
    return '\n'.join(lines)
