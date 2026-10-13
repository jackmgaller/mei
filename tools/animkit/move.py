"""Moves (MECH/MOVE.anim.json): loading (with a base move to start from), checking the format,
and sampling them frame by frame: each part's matrix, the boxes, the marks and the root motion.
The format is documented in docs/ANIMKIT.md ("The move format")."""
import copy
import math
from pathlib import Path

from kitcore import jsonio
from .rig import AnimError, load_rig, fight_xy, apply, mul, rot_xyz, PARTS

FORMAT = 'mei-anim'
EASES = ('linear', 'ease', 'in', 'out', 'hold')
KINDS = {'hit': 0, 'hurt': 1, 'push': 2}
MARKS = {'cancel': 1, 'invuln': 2, 'armour': 4, 'flash': 8, 'step': 16, 'release': 32, 'riposte': 64, 'parry': 128,
         'nopush': 256, 'hide': 512, 'charge': 1024}
TOP = {'format', 'version', 'name', 'rig', 'base', 'retime', 'length', 'loop', 'air', 'travel', 'phases', 'boxes',
       'keys', 'marks', 'motion', 'plant', 'allow', 'design', 'note'}
KEY = {'at', 'from', 'relative', 'ease', 'reach_ease', 'pose', 'offset', 'floor', 'aim', 'reach', 'boxes', 'note',
       'remove'}
BOX = {'kind', 'part', 'min', 'max', 'rect', 'split', 'hit', 'grow', 'note'}
POSE_FIELDS = ('pose', 'offset', 'from', 'aim', 'floor')
MAX_LENGTH = 600
MAX_ANGLE = 360.0
MAX_BOXES = 16          # anim.akr's ANIM_MAX_BOXES
BOX_ROUND = 256         # boxes are rounded to 1/256 m
MAX_TRAVEL = 2.0        # m a frame
AIM_BEND = 100.0        # degrees a wrist solved by "aim" may turn before a warning


def ease(kind, t):
    if kind == 'hold':
        return 0.0
    if kind == 'in':
        return t*t
    if kind == 'out':
        return 1-(1-t)*(1-t)
    if kind == 'ease':
        return t*t*(3-2*t)
    return t


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def need(cond, path, message):
    if not cond:
        raise AnimError(path, message)


# ---- loading, with "base"

def load_data(path, seen=()):
    """The move's JSON with its base merged in, every path made absolute."""
    path = Path(path).resolve()
    need(path not in seen, '/base', f'The bases loop: {" -> ".join(str(p) for p in seen)} -> {path}.')
    need(path.is_file(), '/base' if seen else '/input', f'No move at {path}.')
    data = jsonio.load(str(path), AnimError)
    need(isinstance(data, dict), '/', 'A move is a JSON object.')
    need(data.get('format') == FORMAT, '/format', f'A move has "format": "{FORMAT}".')
    unknown = sorted(set(data)-TOP)
    if unknown:
        raise AnimError('/'+unknown[0], f'Unknown field {unknown[0]!r}; a move has {", ".join(sorted(TOP))}.')
    if 'rig' in data:
        need(isinstance(data['rig'], str), '/rig', 'rig is a path to a .rig.json, relative to this file.')
        data['rig'] = str((path.parent/data['rig']).resolve())
    if not data.get('base'):
        data.pop('base', None)
        return data
    need(isinstance(data['base'], str), '/base', 'base is a path to another move, relative to this file.')
    base = load_data(path.parent/data['base'], seen+(path,))
    return merge(base, data)


def merge_key(old, key):
    """A key merged over another at the same frame: pose and boxes by name, other fields replaced."""
    new = copy.deepcopy(old)
    for f, v in key.items():
        if f in ('pose', 'boxes') and isinstance(v, dict):
            d = dict(new.get(f) or {})
            d.update(copy.deepcopy(v))
            new[f] = d
        else:
            new[f] = copy.deepcopy(v)
    return new


def retime_map(pairs):
    """The frame map of a "retime": [[old, new], ...]: piecewise linear between the pairs, rounded
    to the nearest frame (halves up), and shifted one for one before the first and after the last."""
    need(isinstance(pairs, list) and pairs and all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                                                    for v in p) for p in pairs), '/retime',
         'retime is a list of [base frame, new frame] pairs: [[0, 0], [11, 9], [38, 34]].')
    for i in range(1, len(pairs)):
        need(pairs[i][0] > pairs[i-1][0] and pairs[i][1] >= pairs[i-1][1], f'/retime/{i}',
             'The pairs go in order of the base\'s frames, and the new frames do not go back.')

    def f(x):
        if x <= pairs[0][0]:
            v = pairs[0][1]+(x-pairs[0][0])
        elif x >= pairs[-1][0]:
            v = pairs[-1][1]+(x-pairs[-1][0])
        else:
            k = 0
            while pairs[k+1][0] < x:
                k += 1
            (a, na), (b, nb) = pairs[k], pairs[k+1]
            v = math.floor(na+(x-a)*(nb-na)/(b-a)+0.5)
        need(v >= 0, '/retime', f'The retime takes the base\'s frame {x} to {v}, before the move starts.')
        return v
    return f


def retime(base, pairs):
    """The base move with its keys, motion, plants and marks moved by the retime's frame map, and
    its length the last frame's new place + 1. Base keys that land on one frame merge, the later
    over the earlier."""
    f = retime_map(pairs)
    out = copy.deepcopy(base)
    keys = {}
    for key in base.get('keys', []):
        if not isinstance(key, dict) or not isinstance(key.get('at'), int):
            continue
        key = dict(key, at=f(key['at']))
        keys[key['at']] = merge_key(keys[key['at']], key) if key['at'] in keys else key
    out['keys'] = [keys[a] for a in sorted(keys)]
    motion = []
    for m in base.get('motion', []):
        if isinstance(m, dict) and isinstance(m.get('from'), int) and isinstance(m.get('to'), int):
            a = f(m['from'])
            m = dict(m, **{'from': a, 'to': max(f(m['to']), a+1)})
        motion.append(m)
    if 'motion' in base:
        out['motion'] = motion

    def frames(r):
        if isinstance(r, int):
            return f(r)
        if isinstance(r, list) and len(r) == 2 and all(isinstance(v, int) for v in r):
            return [f(r[0]), f(r[1])]
        return r
    if isinstance(base.get('plant'), dict):
        out['plant'] = {end: [frames(r) for r in rs] if isinstance(rs, list) else rs for end, rs in base['plant'].items()}
    if isinstance(base.get('marks'), dict):
        out['marks'] = {n: [frames(r) for r in rs] if isinstance(rs, list) else rs for n, rs in base['marks'].items()}
    if isinstance(base.get('length'), int):
        out['length'] = f(base['length']-1)+1
    return out


def merge(base, over):
    if 'retime' in over:
        base = retime(base, over['retime'])
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k in ('base', 'retime', 'boxes', 'marks', 'keys', 'allow'):
            continue
        out[k] = copy.deepcopy(v)
    if 'allow' in over:
        need(isinstance(over['allow'], list), '/allow', 'allow is a list of pairs of parts.')
        pairs = list(out.get('allow') or [])
        have = [frozenset(p) for p in pairs if isinstance(p, list)]
        for p in over['allow']:
            if not (isinstance(p, list) and frozenset(p) in have):
                pairs.append(copy.deepcopy(p))
                if isinstance(p, list):
                    have.append(frozenset(p))
        out['allow'] = pairs
    for k in ('boxes', 'marks'):
        if k in over:
            need(isinstance(over[k], dict), '/'+k, f'{k} is an object.')
            merged = dict(out.get(k) or {})
            merged.update(copy.deepcopy(over[k]))
            out[k] = merged
    if 'keys' in over:
        need(isinstance(over['keys'], list), '/keys', 'keys is a list.')
        keys = {k.get('at'): k for k in out.get('keys', []) if isinstance(k, dict)}
        for k, key in enumerate(over['keys']):
            need(isinstance(key, dict) and number(key.get('at')), f'/keys/{k}/at', 'Every key has "at": its frame.')
            if key.get('remove'):
                keys.pop(key['at'], None)
                continue
            old = keys.get(key['at'])
            keys[key['at']] = copy.deepcopy(key) if old is None else merge_key(old, key)
        out['keys'] = [keys[a] for a in sorted(keys)]
    return out


def _turn(a, b):
    """The 3 x 3 rotation that takes unit vector a to unit vector b by the shortest turn."""
    na, nb = math.sqrt(sum(v*v for v in a)), math.sqrt(sum(v*v for v in b))
    a, b = [v/na for v in a], [v/nb for v in b]
    c = max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b))))
    w = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    s = math.sqrt(sum(v*v for v in w))
    if s < 1e-9:
        if c > 0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        # opposite: half a turn about any axis square to a
        w = (0.0, -a[2], a[1]) if abs(a[0]) < 0.9 else (-a[2], 0.0, a[0])
        s = math.sqrt(sum(v*v for v in w))
        c = -1.0
    x, y, z = (v/s for v in w)
    sn, cs = math.sqrt(max(0.0, 1-c*c)), c
    t = 1-cs
    return [[t*x*x+cs, t*x*y-sn*z, t*x*z+sn*y],
            [t*x*y+sn*z, t*y*y+cs, t*y*z-sn*x],
            [t*x*z-sn*y, t*y*z+sn*x, t*z*z+cs]]


def _euler(r, near):
    """[x, y, z] degrees with rot_xyz() == r (R = Rz Ry Rx), of the two solutions the one nearest
    near, each angle within 180 degrees of near's."""
    def wrap(v, to):
        return v-360.0*round((v-to)/360.0)
    sb = max(-1.0, min(1.0, -r[2][0]))
    b = math.degrees(math.asin(sb))
    if math.sqrt(r[2][1]**2+r[2][2]**2) > 1e-6:
        a = math.degrees(math.atan2(r[2][1], r[2][2]))
        c = math.degrees(math.atan2(r[1][0], r[0][0]))
        options = [(a, b, c), (a+180.0, 180.0-b, c+180.0)]
    elif sb > 0:            # y = 90: only x - z is fixed
        diff = math.degrees(math.atan2(r[0][1], r[0][2]))
        options = [(near[0], 90.0, near[0]-diff)]
    else:                   # y = -90: only x + z is fixed
        total = math.degrees(math.atan2(-r[0][1], -r[0][2]))
        options = [(near[0], -90.0, total-near[0])]
    best = None
    for o in options:
        o = [wrap(v, n) for v, n in zip(o, near)]
        cost = sum(abs(v-n) for v, n in zip(o, near))
        if best is None or cost < best[0]:
            best = (cost, o)
    return best[1]


# ---- a checked, resolved move

class Move:
    """A move resolved against its rig: full poses at its keys, its box sets, marks and motion.
    errors: problems with the format (the move cannot be sampled while there are any)."""

    def __init__(self, path, rig=None, name=None):
        self.path = Path(path).resolve()
        self.data = load_data(self.path)
        d = self.data
        self.name = name or d.get('name') or self.path.name.split('.')[0]
        rig_path = rig or d.get('rig')
        need(rig_path, '/rig', 'A move names its rig ("rig": "../../models/hero/hero.rig.json").')
        self.rig = load_rig(rig_path)
        self.warnings = []
        self._check()

    def warn(self, path, message, check='format'):
        self.warnings.append({'check': check, 'path': path, 'message': message})

    def _check(self):
        d, rig = self.data, self.rig
        need(isinstance(d.get('length'), int) and 1 <= d['length'] <= MAX_LENGTH, '/length',
             f'length is the move\'s frames at 60 a second, 1 to {MAX_LENGTH}.')
        self.length = d['length']
        self.loop = bool(d.get('loop', False))
        self.air = bool(d.get('air', False))
        keys = d.get('keys')
        need(isinstance(keys, list) and keys, '/keys', 'A move has at least one key.')
        last = -1
        self.boxes0 = self._boxes(d.get('boxes', {}), '/boxes', {})
        self.pose_keys = []          # (frame, ease, rotate {id: [x, y, z]}, offset [f, u])
        self.box_keys = [(0, self.boxes0)]
        guard = rig.poses.get('guard', {'rotate': {}, 'offset': [0.0, 0.0]})
        cur_rot = dict(guard['rotate'])
        cur_off = list(guard['offset'])
        off_from = None              # the pose key whose offset the current one is (for "floor")
        self.offset_from = []        # per pose key: that key's index, or None (a rig's pose)
        self.floor_keys = []         # pose key indices with "floor": true
        self.keyed = {}              # {joint: [frames of the pose keys that name it]}
        self.aims = []               # (frame, part, wrist, angles) solved by "aim"
        self.key_index = {}          # {frame: index in keys}
        boxes = self.boxes0
        self.reach = {}             # {end: [(frame, ease, [forward, up] or None: the track ends)]}
        for k, key in enumerate(keys):
            p = f'/keys/{k}'
            need(isinstance(key, dict), p, 'A key is an object.')
            unknown = sorted(set(key)-KEY)
            if unknown:
                raise AnimError(p, f'Unknown field {unknown[0]!r} in a key; a key has {", ".join(sorted(KEY))}.')
            at = key.get('at')
            need(isinstance(at, int), p+'/at', 'at is the key\'s frame, a whole number.')
            need(at > last, p+'/at', f'Keys are in order of their frames, each once: frame {at} comes after {last}.')
            need(0 <= at < self.length or (at == self.length and not any(f in key for f in POSE_FIELDS)), p+'/at',
                 f'Frame {at} is outside the move (frames 0 to {self.length-1}).')
            last = at
            self.key_index[at] = k
            is_pose = any(f in key for f in POSE_FIELDS)
            if k == 0:
                need(at == 0, p+'/at', 'The first key is at frame 0.')
                is_pose = True
            relative = key.get('relative', False)
            need(isinstance(relative, bool), p+'/relative', 'relative is true or false: the key\'s angles and offset '
                 'are added to the guard\'s.')
            need(not relative or 'guard' in rig.poses, p+'/relative', f'The rig {rig.name} has no guard pose.')
            if 'from' in key:
                need(key['from'] in rig.poses, p+'/from',
                     f'{key["from"]!r} is not one of the rig\'s poses ({", ".join(rig.poses) or "none"}).')
                cur_rot = dict(rig.poses[key['from']]['rotate'])
                cur_off = list(rig.poses[key['from']]['offset'])
                off_from = None
            if 'pose' in key:
                need(isinstance(key['pose'], dict), p+'/pose', 'pose is an object: {"part id": [x, y, z] degrees}.')
                cur_rot = dict(cur_rot)
                for j, r in key['pose'].items():
                    need(j in PARTS, f'{p}/pose/{j}', f'{j!r} is not a part ({", ".join(PARTS)}).')
                    need(isinstance(r, list) and len(r) == 3 and all(number(v) for v in r), f'{p}/pose/{j}',
                         'A rotation is [x, y, z] in degrees.')
                    need(all(abs(v) <= MAX_ANGLE for v in r), f'{p}/pose/{j}', f'Angles are within +-{MAX_ANGLE:g} degrees.')
                    if j not in rig.joints:
                        self.warn(f'{p}/pose/{j}', f'The rig {rig.name} has no {j}; the rotation does nothing.')
                    if relative:
                        g = guard['rotate'].get(j, [0.0, 0.0, 0.0])
                        cur_rot[j] = [a+float(v) for a, v in zip(g, r)]
                    else:
                        cur_rot[j] = [float(v) for v in r]
                    self.keyed.setdefault(j, []).append(at)
            if 'offset' in key:
                o = key['offset']
                need(isinstance(o, list) and len(o) == 2 and all(number(v) for v in o), p+'/offset',
                     'offset is [forward, up] in metres: the pelvis moved from its rest place.')
                need(all(abs(v) < 30 for v in o), p+'/offset', 'An offset is within 30 m.')
                cur_off = [a+float(v) for a, v in zip(guard['offset'], o)] if relative else [float(v) for v in o]
            if 'aim' in key:
                need(isinstance(key['aim'], dict), p+'/aim', 'aim is {"weapon_r": [elevation, yaw]} in degrees.')
                cur_rot = dict(cur_rot)
                for part, v in key['aim'].items():
                    q = f'{p}/aim/{part}'
                    need(part in rig.joints and rig.joints[part]['parent'] and rig.joints[rig.joints[part]['parent']]['parent'],
                         q, f'{part!r} is not a part of the rig {rig.name} below a wrist (weapon_r, weapon_l).')
                    need(isinstance(v, list) and len(v) == 2 and all(number(x) for x in v) and abs(v[0]) <= 90
                         and abs(v[1]) <= 180, q, 'An aim is [elevation, yaw] in degrees: elevation -90 (down) to 90 (up), '
                         'yaw -180 to 180 (0 forward, +90 to the mech\'s left, -90 to its right).')
                    wrist = rig.joints[part]['parent']
                    cur_rot[wrist] = self._aim(cur_rot, part, float(v[0]), float(v[1]))
                    self.keyed.setdefault(wrist, []).append(at)
                    self.aims.append((at, part, wrist, cur_rot[wrist]))
                    r = rot_xyz(cur_rot[wrist])
                    bend = math.degrees(math.acos(max(-1.0, min(1.0, (r[0][0]+r[1][1]+r[2][2]-1)/2))))
                    if bend > AIM_BEND:
                        self.warn(q, f'The aim turns {wrist} {bend:.0f} degrees from straight (to {cur_rot[wrist]}): '
                                     f'turn the forearm toward the aim so the wrist bends less.', 'aim')
            if 'offset' in key or key.get('floor'):
                off_from = len(self.pose_keys)
            if 'floor' in key:
                need(key['floor'] is True or key['floor'] is False, p+'/floor',
                     'floor is true: the pelvis is set so the lowest part touches the floor.')
            e = key.get('ease', 'ease')
            need(e in EASES, p+'/ease', f'ease is one of {", ".join(EASES)}.')
            re = key.get('reach_ease', e)
            need(re in EASES, p+'/reach_ease', f'reach_ease is one of {", ".join(EASES)}.')
            if 'reach' in key:
                need(isinstance(key['reach'], dict), p+'/reach', 'reach is {"foot_l": [forward, up]}: where the joint goes, '
                     'from its place in the rest pose (fight-local metres); "guard": its place in the guard; null: '
                     'the track ends.')
                for end, v in key['reach'].items():
                    self._chain(end, f'{p}/reach/{end}')
                    if v is None:
                        need(end in self.reach and self.reach[end][-1][2] is not None, f'{p}/reach/{end}',
                             f'null ends a reach track, but {end} has none going.')
                        self.reach[end].append((at, re, None))
                        continue
                    if v == 'guard':
                        v = self.guard_reach(end, f'{p}/reach/{end}')
                    need(isinstance(v, list) and len(v) == 2 and all(number(x) for x in v) and all(abs(x) < 20 for x in v),
                         f'{p}/reach/{end}', 'A reach is [forward, up] in metres from the joint\'s rest place, '
                         '"guard", or null.')
                    self.reach.setdefault(end, []).append((at, re, [float(x) for x in v]))
            if is_pose:
                self.pose_keys.append((at, e, dict(cur_rot), list(cur_off)))
                self.offset_from.append(off_from)
                if key.get('floor'):
                    self.floor_keys.append(len(self.pose_keys)-1)
            if 'boxes' in key:
                boxes = self._boxes(key['boxes'], p+'/boxes', boxes)
                if self.box_keys[-1][0] == at:
                    self.box_keys[-1] = (at, boxes)
                else:
                    self.box_keys.append((at, boxes))
        # marks
        self.marks = [0]*self.length
        marks = d.get('marks', {})
        need(isinstance(marks, dict), '/marks', 'marks is an object: {"cancel": [[from, to]], "step": [12, 30]}.')
        for name, ranges in marks.items():
            p = '/marks/'+name
            need(name in MARKS, p, f'{name!r} is not a mark ({", ".join(MARKS)}).')
            need(isinstance(ranges, list), p, 'A mark is a list of frames and [from, to] ranges (inclusive).')
            for i, r in enumerate(ranges):
                lo, hi = (r, r) if isinstance(r, int) else (r[0], r[1]) if (
                    isinstance(r, list) and len(r) == 2 and all(isinstance(v, int) for v in r)) else (None, None)
                need(lo is not None and 0 <= lo <= hi < self.length, f'{p}/{i}',
                     f'A mark\'s frame or [from, to] is within the move (0 to {self.length-1}), from <= to.')
                for f in range(lo, hi+1):
                    self.marks[f] |= MARKS[name]
        # motion
        self.motion = []
        for i, m in enumerate(d.get('motion', [])):
            p = f'/motion/{i}'
            need(isinstance(m, dict) and isinstance(m.get('from'), int) and isinstance(m.get('to'), int)
                 and 0 <= m['from'] < m['to'] <= self.length, p,
                 f'A motion is {{"from": frame, "to": frame, "by": [forward, up]}}, 0 <= from < to <= {self.length}.')
            by = m.get('by')
            need(isinstance(by, list) and len(by) == 2 and all(number(v) for v in by) and all(abs(v) < 60 for v in by),
                 p+'/by', 'by is [forward, up] in metres over the range.')
            e = m.get('ease', 'linear')
            need(e in EASES and e != 'hold', p+'/ease', 'A motion\'s ease is linear, ease, in or out.')
            self.motion.append((m['from'], m['to'], by, e))
        travel = d.get('travel', 0)
        need(number(travel) and abs(travel) <= MAX_TRAVEL, '/travel',
             f'travel is the metres a frame the fight moves the root forward (negative: back), within {MAX_TRAVEL:g}.')
        self.travel = float(travel)
        # phases
        self.phases = None
        ph = d.get('phases')
        if ph is not None:
            need(isinstance(ph, dict) and set(ph) == {'startup', 'active', 'recovery'}
                 and all(isinstance(v, int) and v >= 0 for v in ph.values()), '/phases',
                 'phases is {"startup": frames, "active": frames, "recovery": frames}.')
            self.phases = ph
        # plants: {end part: [(from, to)]}, a two-joint chain held in place
        self.plants = {}
        plant = d.get('plant', {})
        need(isinstance(plant, dict), '/plant', 'plant is an object: {"foot_l": [[from, to]], ...}.')
        for end, ranges in plant.items():
            p = '/plant/'+end
            top, mid = self._chain(end, p)
            need(isinstance(ranges, list), p, 'A plant is a list of [from, to] ranges (inclusive).')
            spans = []
            for i, r in enumerate(ranges):
                need(isinstance(r, list) and len(r) == 2 and all(isinstance(v, int) for v in r)
                     and 0 <= r[0] <= r[1] < self.length, f'{p}/{i}',
                     f'A plant range is [from, to], 0 <= from <= to < {self.length}.')
                need(not spans or r[0] > spans[-1][1], f'{p}/{i}', 'A part\'s plant ranges are in order and apart.')
                spans.append((r[0], r[1]))
            self.plants[end] = (top, mid, spans)
        self._plant_cache = {}
        # the design's numbers (MOVES.md) the boxes are checked against
        self.design = d.get('design')
        if self.design is not None:
            dz = self.design
            need(isinstance(dz, dict) and set(dz) <= {'hit', 'tolerance', 'note'}, '/design',
                 'design is {"hit": [x0, y0, x1, y1], "tolerance": metres}: what the move\'s hit boxes should span.')
            h = dz.get('hit')
            need(isinstance(h, list) and len(h) == 4 and all(number(v) for v in h) and h[0] < h[2] and h[1] < h[3],
                 '/design/hit', 'hit is [x0, y0, x1, y1]: the extent of the move\'s hit boxes over its active frames.')
            need(number(dz.get('tolerance', 0.5)) and dz.get('tolerance', 0.5) >= 0, '/design/tolerance',
                 'tolerance is metres (default 0.5).')
        self.allow = set(rig.allow)
        for i, pair in enumerate(d.get('allow', [])):
            need(isinstance(pair, list) and len(pair) == 2 and all(isinstance(s, str) for s in pair), f'/allow/{i}',
                 'allow lists pairs of parts ["forearm_r", "torso"] (or part/node ids) that may pass through each other.')
            self.allow.add(frozenset(pair))
        self._floor()
        self._overrides()

    def guard_reach(self, end, p):
        """A reach's "guard": where the rig's guard pose puts the joint, [forward, up] from its rest
        place to the centimetre; a foot's on the floor (up 0)."""
        need('guard' in self.rig.poses, p, f'The rig {self.rig.name} has no guard pose.')
        g = self.rig.poses['guard']
        m = self.rig.pose_matrices(g['rotate'], g['offset'])[end]
        rx, ry, rz = self.rest_joint(end)
        forward, up = -(m[2][3]-rz), m[1][3]-ry
        return [round(forward, 2), 0.0 if end.startswith('foot') else round(up, 2)]

    def _aim(self, rot, part, elevation, yaw):
        """The wrist's rotation (part's parent) that points part's +Y (a weapon's blade) at
        [elevation, yaw] in the root's frame, turned from the wrist's current rotation as little as
        possible (so the blade's roll follows the key); rounded to 0.01 degree."""
        rig = self.rig
        wrist = rig.joints[part]['parent']
        mats = rig.pose_matrices(rot)
        arm = mats[rig.joints[wrist]['parent']]
        wj = rig.joints[wrist]
        frame = mul(arm, rot_xyz(wj['rest'])) if wj['rest'] else arm
        pj = rig.joints[part]
        local = rot_xyz(pj['rest']) if pj['rest'] else ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0))
        if rot.get(part) and any(rot[part]):
            local = mul(local, rot_xyz(rot[part]))
        axis = (local[0][1], local[1][1], local[2][1])          # the part's +Y in the wrist's frame
        e, y = math.radians(elevation), math.radians(yaw)
        d = (math.cos(e)*math.sin(y), math.sin(e), -math.cos(e)*math.cos(y))
        u = tuple(sum(frame[i][k]*d[i] for i in range(3)) for k in range(3))       # d in the wrist's frame
        cur = list(rot.get(wrist, [0.0, 0.0, 0.0]))
        r0 = rot_xyz(cur)
        v0 = tuple(sum(r0[k][i]*axis[i] for i in range(3)) for k in range(3))
        q = _turn(v0, u)
        r = [[sum(q[i][k]*r0[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        return [round(a, 2) for a in _euler(r, cur)]

    def _chain(self, end, p):
        """(top, mid): the two joints above end that plant and reach turn."""
        need(end in self.rig.joints, p, f'{end!r} is not a part of the rig {self.rig.name}.')
        mid = self.rig.joints[end]['parent']
        top = self.rig.joints[mid]['parent'] if mid else None
        need(top is not None and self.rig.joints[top]['parent'] is not None, p,
             f'{end} is not at the end of a chain of two joints (as a foot is: thigh, shin, foot).')
        return top, mid

    def _boxes(self, spec, path, current):
        need(isinstance(spec, dict), path, 'boxes is an object: {"name": box, or null to remove it}.')
        out = dict(current)
        for name, b in spec.items():
            p = f'{path}/{name}'
            if b is None:
                out.pop(name, None)
                continue
            need(isinstance(b, dict), p, 'A box is an object (or null to remove it).')
            unknown = sorted(set(b)-BOX)
            if unknown:
                raise AnimError(p, f'Unknown field {unknown[0]!r} in a box; a box has {", ".join(sorted(BOX))}.')
            need(b.get('kind') in KINDS, p+'/kind', 'kind is hit, hurt or push.')
            box = {'kind': b['kind'], 'hit': b.get('hit', 0), 'grow': b.get('grow', 0.0), 'split': b.get('split', 1)}
            need(isinstance(box['hit'], int) and 0 <= box['hit'] < 8, p+'/hit', 'hit is which hit of the move it is, 0-7.')
            need(number(box['grow']) and abs(box['grow']) <= 2, p+'/grow', 'grow is metres, within 2.')
            need(isinstance(box['split'], int) and 1 <= box['split'] <= 6, p+'/split', 'split is 1-6 boxes.')
            if 'rect' in b:
                r = b['rect']
                need('part' not in b and isinstance(r, list) and len(r) == 4 and all(number(v) for v in r)
                     and r[0] < r[2] and r[1] < r[3], p+'/rect',
                     'rect is [x0, y0, x1, y1] from the root (fight-local metres), x0 < x1, y0 < y1, without a part.')
                box['rect'] = [float(v) for v in r]
                box['part'] = 'pelvis'
            else:
                part = b.get('part')
                need(part in PARTS, p+'/part', f'A box follows a part ({", ".join(PARTS)}) or is a rect.')
                need(part in self.rig.joints, p+'/part', f'The rig {self.rig.name} has no {part}.')
                box['part'] = part
                if 'min' in b or 'max' in b:
                    lo = b.get('min')
                    hi = b.get('max')
                    need(isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3
                         and all(number(v) for v in lo+hi) and all(a < c for a, c in zip(lo, hi)), p,
                         'min and max are the box\'s corners in the part\'s frame, [x, y, z] each, min < max.')
                    box['local'] = (tuple(float(v) for v in lo), tuple(float(v) for v in hi))
                else:
                    bounds = self.rig.bounds(part)
                    need(bounds, p, f'{part} has no bounds in the rig; give min and max.')
                    box['local'] = bounds
            out[name] = box
        return out

    # ---- sampling

    def pose_at(self, f):
        """(rotate, offset) at frame f (a number: fractional frames interpolate)."""
        keys = self.pose_keys
        if self.loop:
            f = f % self.length
        k = 0
        while k+1 < len(keys) and keys[k+1][0] <= f:
            k += 1
        a = keys[k]
        if k+1 < len(keys):
            b = keys[k+1]
            span = b[0]-a[0]
        elif self.loop and len(keys) > 1:
            b = keys[0]
            span = self.length-a[0]
        else:
            return a[2], a[3]
        t = ease(a[1], (f-a[0])/span)
        rot = {}
        for j in set(a[2]) | set(b[2]):
            ra, rb = a[2].get(j, [0, 0, 0]), b[2].get(j, [0, 0, 0])
            rot[j] = [x+(y-x)*t for x, y in zip(ra, rb)]
        return rot, [x+(y-x)*t for x, y in zip(a[3], b[3])]

    def matrices(self, f):
        rot, off = self.pose_at(f)
        mats = self.rig.pose_matrices(rot, off)
        for end, track in self.reach.items():
            if any(a <= f <= b for a, b in self.plants.get(end, (None, None, []))[2]):
                continue
            want = self._reach_at(end, track, f)
            if want:
                top, mid = self._chain(end, '/reach')
                self._solve(mats, rot, end, top, mid, want, self._level(end, mats[end]))
        for end, (top, mid, spans) in self.plants.items():
            for a, b in spans:
                if a <= f <= b:
                    self._plant(mats, rot, end, top, mid, a, f)
        return mats

    def rest_joint(self, end):
        if not hasattr(self, '_rest'):
            self._rest = self.rig.pose_matrices({}, (0.0, 0.0))
        m = self._rest[end]
        return m[0][3], m[1][3], m[2][3]

    def _reach_at(self, end, track, f):
        """The (y, z) a reach track puts end's joint at on frame f (root frame), or None outside it.
        A null entry ends the track: the value before it holds until it."""
        if not track[0][0] <= f <= track[-1][0]:
            return None
        k = 0
        while k+1 < len(track) and track[k+1][0] <= f:
            k += 1
        at, e, v = track[k]
        if v is None:
            return None
        if k+1 < len(track) and track[k+1][2] is not None:
            b = track[k+1]
            t = ease(e, (f-at)/(b[0]-at))
            v = [x+(y-x)*t for x, y in zip(v, b[2])]
        rx, ry, rz = self.rest_joint(end)
        return (ry+v[1], rz-v[0])

    def _level(self, end, m):
        """A foot's rotation made level (its heading kept); another part's as it is."""
        r = [list(m[i][:3]) for i in range(3)]
        if not end.startswith('foot'):
            return r
        fx, fz = -r[0][2], -r[2][2]
        n = math.hypot(fx, fz) or 1.0
        fx, fz = fx/n, fz/n
        # a turn about Y that takes -Z to (fx, 0, fz)
        return [[-fz, 0.0, -fx], [0.0, 1.0, 0.0], [fx, 0.0, -fz]]

    def root_travel(self, f):
        """The root's motion from frame 0 to frame f, (forward, up) metres."""
        if not hasattr(self, '_travel'):
            x = y = 0
            self._travel = [(0, 0)]
            for dx, dy in self.motion_raw():
                x += dx
                y += dy
                self._travel.append((x, y))
        f = min(max(int(f), 0), self.length)
        x, y = self._travel[f]
        return x/65536+self.travel*f, y/65536

    def solved(self, end):
        """The frames on which end's chain is solved (a reach track or a plant), and the plants'
        first frames (where the keyed pose decides the planted place)."""
        frames, starts = set(), set()
        track = self.reach.get(end)
        if track:
            frames |= {f for f in range(self.length) if self._reach_at(end, track, f)}
        for a, b in self.plants.get(end, (None, None, []))[2]:
            frames |= set(range(a, b+1))
            starts.add(a)
        return frames, starts

    def lowest(self, f, mats=None):
        """(height, part): the lowest point of the posed parts on frame f over the floor (y = 0
        under the root, which motion may have lifted)."""
        mats = mats or self.matrices(f)
        lift = self.root_travel(f)[1]
        best = (math.inf, None)
        for pid, px in self.rig.proxies().items():
            m = mats[pid]
            y = lift+min(m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2]+m[1][3] for v in px['points'])
            best = min(best, (y, pid))
        return best

    def _floor(self):
        """Keys with "floor": true: the offset's up set so the lowest part touches the floor on
        the key's frame (and on the keys that carry that offset)."""
        self.floor_report = []
        for k in self.floor_keys:
            at = self.pose_keys[k][0]
            for _ in range(12):
                self._plant_cache = {}
                y, who = self.lowest(at)
                if abs(y) < 1e-4:
                    break
                for i, src in enumerate(self.offset_from):
                    if src == k or i == k:
                        self.pose_keys[i][3][1] -= y
            y, who = self.lowest(at)
            if abs(y) > 0.005:
                self.warn('/keys', f'"floor" on frame {at} cannot bring the lowest part to the floor ({who} stays '
                               f'{y:+.2f} m): it is held by a plant or a reach.', 'floor')
            self.floor_report.append((at, round(self.pose_keys[k][3][1], 4), who))
        self._plant_cache = {}

    def _overrides(self):
        """Warnings for knee and hip bends keyed by hand that never show: a pose key naming the
        upper joints of a chain (thigh, shin) that a reach track or a plant solves about X on
        every frame the key reaches (from the pose key before it to the one after)."""
        frames_of = [k[0] for k in self.pose_keys]
        for end in sorted(set(self.reach) | set(self.plants)):
            top, mid = self._chain(end, '/reach')
            solved, starts = self.solved(end)
            lost = {}
            for j in (top, mid):
                for at in self.keyed.get(j, []):
                    i = frames_of.index(at)
                    lo = frames_of[i-1]+1 if i > 0 else 0
                    if i+1 < len(frames_of):
                        span = range(lo, frames_of[i+1])
                    elif self.loop and len(frames_of) > 1:
                        span = [f % self.length for f in range(lo, self.length+frames_of[0])]
                    else:
                        span = range(lo, self.length)
                    if at not in starts and all(f in solved for f in span):
                        lost.setdefault(at, []).append(j)
            if lost:
                joints = sorted({j for js in lost.values() for j in js}, key=(top, mid).index)
                what = 'reach' if end in self.reach else 'plant'
                self.warn(f'/keys/{self.key_index[min(lost)]}/pose',
                          f'{" and ".join(joints)} {"is" if len(joints) == 1 else "are"} keyed on frame'
                          f'{"s" if len(lost) > 1 else ""} {", ".join(str(f) for f in sorted(lost))}, but {end}\'s '
                          f'{what} solves {"its" if len(joints) == 1 else "their"} X angle on every frame those keys '
                          f'reach: the keyed X never shows (Y and Z do). If the keyed bend is the one wanted, end '
                          f'the {what} sooner' + (f' ("reach": {{"{end}": null}})' if what == 'reach' else '') + '.',
                          'legs')
    def _plant_target(self, end, a):
        """Where a plant holds its part: the part's matrix at frame a as keyed (a foot set on the
        floor, level, keeping its heading), and the root's travel then."""
        key = (end, a)
        if key not in self._plant_cache:
            rot, off = self.pose_at(a)
            m = self.rig.pose_matrices(rot, off)[end]
            # where the frame's pose puts it (reach included), a foot set on the floor and level
            m = self.matrices_unplanted(a)[end]
            r = self._level(end, m)
            pos = [m[0][3], m[1][3], m[2][3]]
            if end.startswith('foot'):
                pos[1] = self.rest_joint(end)[1]
            self._plant_cache[key] = (r, pos, self.root_travel(a))
        return self._plant_cache[key]

    def _plant(self, mats, rot, end, top, mid, a, f):
        """Solves top's and mid's X so end's joint stays where the plant holds it (in the world:
        the root's travel since frame a undone), sets end's rotation to the held one and poses
        what hangs from end again."""
        from .rig import mul, translate, rot_xyz
        r_end, pos, travel0 = self._plant_target(end, a)
        travel = self.root_travel(f)
        want = (pos[1]-(travel[1]-travel0[1]), pos[2]+(travel[0]-travel0[0]))      # (y, z) in the root frame
        self._solve(mats, rot, end, top, mid, want, r_end)

    def matrices_unplanted(self, f):
        saved = self.plants
        self.plants = {}
        try:
            return self.matrices(f)
        finally:
            self.plants = saved

    def _solve(self, mats, rot, end, top, mid, want, r_end):
        """Turns top and mid about their X so end's joint is at want (y, z in the root frame),
        gives end the rotation r_end and poses what hangs from end again."""
        from .rig import mul, translate, rot_xyz
        rig = self.rig
        parent = mats[rig.joints[top]['parent']]

        def local(pid, r):
            j = rig.joints[pid]
            m = translate(j['offset'])
            if j['rest']:
                m = mul(m, rot_xyz(j['rest']))
            return mul(m, rot_xyz(r)) if r and any(r) else m

        rt = list(rot.get(top, [0, 0, 0]))
        rm = list(rot.get(mid, [0, 0, 0]))

        def ends(x, y):
            mt = mul(parent, local(top, [x, rt[1], rt[2]]))
            mm = mul(mt, local(mid, [y, rm[1], rm[2]]))
            me = mul(mm, local(end, [0, 0, 0]))
            return mt, mm, me

        def err(x, y):
            me = ends(x, y)[2]
            return (me[1][3]-want[0], me[2][3]-want[1])

        x, y = rt[0], rm[0]
        for _ in range(30):
            e = err(x, y)
            if abs(e[0]) + abs(e[1]) < 1e-5:
                break
            h = 0.01
            ex, ey = err(x+h, y), err(x, y+h)
            j11, j21 = (ex[0]-e[0])/h, (ex[1]-e[1])/h
            j12, j22 = (ey[0]-e[0])/h, (ey[1]-e[1])/h
            det = j11*j22-j12*j21
            if abs(det) < 1e-9:
                y -= 5.0           # straight leg: bend the knee and try again
                continue
            dx = (e[0]*j22-e[1]*j12)/det
            dy = (j11*e[1]-j21*e[0])/det
            step = max(abs(dx), abs(dy))
            if step > 20:
                dx, dy = dx*20/step, dy*20/step
            x, y = x-dx, y-dy
            if end.startswith('foot'):
                y = min(y, -0.5)     # a knee bends one way
        mt, mm, me = ends(x, y)
        mats[top], mats[mid] = mt, mm
        mats[end] = tuple(tuple(r_end[i])+(me[i][3],) for i in range(3))
        self._repose_below(mats, rot, end)

    def _repose_below(self, mats, rot, pid):
        from .rig import mul, translate, rot_xyz
        for child in self.rig.children(pid):
            j = self.rig.joints[child]
            m = translate(j['offset'])
            if j['rest']:
                m = mul(m, rot_xyz(j['rest']))
            r = rot.get(child)
            if r and any(r):
                m = mul(m, rot_xyz(r))
            mats[child] = mul(mats[pid], m)
            self._repose_below(mats, rot, child)

    def boxes_at(self, f, mats=None):
        """[(name, kind, hit, part, x0, y0, x1, y1)] at frame f, fight-local metres (rounded to 1/256)."""
        f = int(f)
        current = self.box_keys[0][1]
        for at, boxes in self.box_keys:
            if at <= f:
                current = boxes
        mats = mats or self.matrices(f)
        out = []
        q = lambda v: round(v*BOX_ROUND)/BOX_ROUND
        for name in sorted(current, key=lambda n: (KINDS[current[n]['kind']], n)):
            b = current[name]
            g = b['grow']
            if 'rect' in b:
                rects = [b['rect']]
            else:
                lo, hi = b['local']
                n = b['split']
                axis = max(range(3), key=lambda a: hi[a]-lo[a])
                rects = []
                for i in range(n):
                    slo, shi = list(lo), list(hi)
                    slo[axis] = lo[axis]+(hi[axis]-lo[axis])*i/n
                    shi[axis] = lo[axis]+(hi[axis]-lo[axis])*(i+1)/n
                    pts = [fight_xy(apply(mats[b['part']], (x, y, z)))
                           for x in (slo[0], shi[0]) for y in (slo[1], shi[1]) for z in (slo[2], shi[2])]
                    rects.append([min(p[0] for p in pts), min(p[1] for p in pts),
                                  max(p[0] for p in pts), max(p[1] for p in pts)])
            for i, r in enumerate(rects):
                out.append((name if len(rects) == 1 else f'{name}.{i}', b['kind'], b['hit'], b['part'],
                            q(r[0]-g), q(r[1]-g), q(r[2]+g), q(r[3]+g)))
        return out

    def motion_raw(self):
        """The root motion over each frame f (from f to f + 1), as raw 16.16 integers [(dx, dy)]:
        the differences of the rounded total, so they add up to every motion's "by" exactly."""
        def total(f):
            x = y = 0.0
            for a, b, by, e in self.motion:
                t = ease(e, min(max((f-a)/(b-a), 0.0), 1.0))
                x += by[0]*t
                y += by[1]*t
            return round(x*65536), round(y*65536)
        pos = [total(f) for f in range(self.length+1)]
        return [(pos[f+1][0]-pos[f][0], pos[f+1][1]-pos[f][1]) for f in range(self.length)]

    def active_frames(self):
        return [f for f in range(self.length) if any(b[1] == 'hit' for b in self.boxes_at(f))]
