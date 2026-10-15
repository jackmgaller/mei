"""`mei_anim.py verify`: the checks a move must pass before it is exported (docs/ANIMKIT.md,
"verify"). Frame by frame, as the runtime will draw it:

  format       the file, its keys, poses, boxes, marks, motion and plants (errors stop here)
  timing       keys in order inside the move; the phases add up to the length; the active
               frames (those with a hit box) are exactly the phases' active frames
  boxes        a hurt box on every frame, a push box on every frame of a grounded move, at most
               16, none thinner than 0.1 m, none absurdly far from the root
  parts        no two parts pass into each other deeper than the rig's own poses have them (rest
               and guard) plus a tolerance, from boxes fitted to each part's pieces
  floor        nothing below the floor (a grounded move), but what the move's floor_allow allows;
               feet planted where the plant says
  slides       a foot on the floor that moves along it (a warning)
"""
import math

from .move import Move, MAX_BOXES, MARKS
from .rig import AnimError, apply, fight_xy

FLOOR_TOLERANCE = 0.03      # m below y = 0 before a part counts as sunk
PLANT_TOLERANCE = 0.02      # m a planted joint may miss its place
SLIDE = 0.04                # m a foot on the floor may move in a frame before it slides
ON_FLOOR = 0.06             # m: a foot this close to the floor is on it
MIN_BOX = 0.1
FAR = 30.0


def obb(m, lo, hi):
    """(centre, axes, half sizes) of the box lo..hi in a part's frame, posed by m."""
    c = apply(m, tuple((a+b)/2 for a, b in zip(lo, hi)))
    axes = [(m[0][k], m[1][k], m[2][k]) for k in range(3)]
    half = tuple((b-a)/2 for a, b in zip(lo, hi))
    return c, axes, half, math.sqrt(sum(h*h for h in half))


def depth(a, b):
    """How far two boxes pass into each other (0: apart): the least overlap over the separating
    axis test's 15 axes."""
    ca, aa, ha, ra = a
    cb, ab, hb, rb = b
    t = tuple(y-x for x, y in zip(ca, cb))
    dist = math.sqrt(sum(v*v for v in t))
    if dist > ra+rb:
        return 0.0
    axes = list(aa)+list(ab)
    for u in aa:
        for v in ab:
            w = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            n = math.sqrt(sum(x*x for x in w))
            if n > 1e-6:
                axes.append(tuple(x/n for x in w))
    best = math.inf
    for L in axes:
        pa = sum(h*abs(sum(x*y for x, y in zip(ax, L))) for h, ax in zip(ha, aa))
        pb = sum(h*abs(sum(x*y for x, y in zip(ax, L))) for h, ax in zip(hb, ab))
        o = pa+pb-abs(sum(x*y for x, y in zip(t, L)))
        if o <= 0:
            return 0.0
        best = min(best, o)
    return best


def ranges(frames):
    """[3, 4, 5, 9] -> '3-5, 9'."""
    out, start, prev = [], None, None
    for f in sorted(frames):
        if start is None:
            start = prev = f
        elif f == prev+1:
            prev = f
        else:
            out.append(f'{start}-{prev}' if prev > start else str(start))
            start = prev = f
    if start is not None:
        out.append(f'{start}-{prev}' if prev > start else str(start))
    return ', '.join(out)


class Checker:
    def __init__(self, move, tolerance):
        self.move = move
        self.rig = move.rig
        self.tolerance = tolerance
        self.failures, self.warnings = [], []
        self.checks = {}

    def fail(self, check, message, **extra):
        self.failures.append({'check': check, 'message': message, **extra})

    def warn(self, check, message, **extra):
        self.warnings.append({'check': check, 'message': message, **extra})

    # ---- timing

    def timing(self):
        mv = self.move
        active = mv.active_frames()
        self.checks['active_frames'] = ranges(active) or 'none'
        if mv.phases:
            st, ac, rc = (mv.phases[k] for k in ('startup', 'active', 'recovery'))
            if st+ac+rc != mv.length:
                self.fail('timing', f'The phases add up to {st}+{ac}+{rc} = {st+ac+rc} frames; the move is {mv.length}.')
            want = list(range(st, st+ac))
            if active != want:
                missing = sorted(set(want)-set(active))
                extra = sorted(set(active)-set(want))
                parts = []
                if missing:
                    parts.append(f'no hit box on active frame{"s" if len(missing) > 1 else ""} {ranges(missing)}')
                if extra:
                    parts.append(f'a hit box outside the active frames, on {ranges(extra)}')
                self.fail('timing', f'The phases say frames {ranges(want) or "none"} are active, but: '
                          + '; '.join(parts) + '.')
        elif active:
            self.warn('timing', f'Hit boxes on frames {ranges(active)} but no "phases": give startup, active and '
                      'recovery so the timing is checked.')
        if mv.loop and mv.motion:
            self.warn('timing', 'A looping move with root motion moves the root again every loop.')

    # ---- boxes

    def boxes(self, frames):
        mv = self.move
        no_hurt, no_push, thin, far, many = [], [], [], [], []
        for f, (mats, boxes) in enumerate(frames):
            kinds = [b[1] for b in boxes]
            passing = mv.marks[f] & MARKS['nopush']
            if 'hurt' not in kinds and not passing:
                no_hurt.append(f)
            if 'push' not in kinds and not mv.air and not passing:
                no_push.append(f)
            if len(boxes) > MAX_BOXES:
                many.append(f)
            for name, kind, hit, part, x0, y0, x1, y1 in boxes:
                if x1-x0 < MIN_BOX or y1-y0 < MIN_BOX:
                    thin.append((f, name))
                # below the root: 2 m on the ground, 4 m in the air (an air attack cuts down past the feet)
                low = -4.0 if mv.air or mv.root_travel(f)[1] > 0 else -2.0
                if max(abs(x0), abs(x1)) > FAR or y1 > FAR or y0 < low:
                    far.append((f, name))
        if no_hurt:
            self.fail('boxes', f'No hurt box on frame{"s" if len(no_hurt) > 1 else ""} {ranges(no_hurt)}: an '
                      'invulnerable frame is a mark ("invuln"), the hurt boxes stay.')
        if no_push:
            self.warn('boxes', f'No push box on {ranges(no_push)} of a grounded move: the mechs can stand inside each other.')
        if many:
            self.fail('boxes', f'More than {MAX_BOXES} boxes on {ranges(many)} (the runtime keeps the first {MAX_BOXES}).')
        for what, rows, message in (('thin', thin, f'thinner than {MIN_BOX} m'),
                                    ('far', far, f'more than {FAR:g} m from the root, or too far below it '
                                                 '(2 m; 4 m on an "air" move or with the root lifted)')):
            names = sorted({n for _, n in rows})
            for n in names:
                fr = [f for f, m in rows if m == n]
                self.fail('boxes', f'Box {n} is {message} on {ranges(fr)}.')
        hits = [b for _, bs in frames for b in bs if b[1] == 'hit']
        self.checks['boxes'] = {'per_frame_max': max((len(b) for _, b in frames), default=0), 'hit_boxes': len(hits)}
        if hits:
            span = [min(b[4] for b in hits), min(b[5] for b in hits), max(b[6] for b in hits), max(b[7] for b in hits)]
            self.checks['hit_extent'] = [round(v, 2) for v in span]
            if mv.design:
                want = mv.design['hit']
                tol = mv.design.get('tolerance', 0.5)
                sides = ('behind (x0)', 'bottom (y0)', 'reach (x1)', 'top (y1)')
                off = [f'{n} {g:.2f} m, the design {w:g}' for n, g, w in zip(sides, span, want) if abs(g-w) > tol]
                if off:
                    self.fail('design', f'The hit boxes span x {span[0]:.2f} to {span[2]:.2f}, y {span[1]:.2f} to '
                              f'{span[3]:.2f}; the design says x {want[0]:g} to {want[2]:g}, y {want[1]:g} to {want[3]:g} '
                              f'(within {tol:g}): ' + '; '.join(off) + '.')
        elif mv.design:
            self.fail('design', 'The design gives a hit box extent, but the move has no hit box.')

    # ---- parts passing into each other

    def pairs(self):
        rig, mv = self.rig, self.move
        prox = rig.proxies()
        parts = [p for p in rig.order if p in prox]
        out = []
        for i, a in enumerate(parts):
            for b in parts[i+1:]:
                ja, jb = rig.joints[a], rig.joints[b]
                if ja['parent'] == b or jb['parent'] == a:
                    continue
                if ja['parent'] == jb['parent'] and ja['offset'] == jb['offset']:
                    continue            # two parts on one joint (a pauldron and its upper arm)
                if frozenset((a, b)) in mv.allow:
                    continue
                for na, la, ha in prox[a]['boxes']:
                    for nb, lb, hb in prox[b]['boxes']:
                        if frozenset((f'{a}/{na}', f'{b}/{nb}')) in mv.allow:
                            continue
                        out.append((a, na, la, ha, b, nb, lb, hb))
        return out

    def parts(self, frames):
        rig = self.rig
        pairs = self.pairs()
        # what the rig's own poses allow
        base = {}
        for name in ['rest']+list(rig.poses):
            p = rig.poses.get(name, {'rotate': {}, 'offset': [0.0, 0.0]})
            mats = rig.pose_matrices(p['rotate'], p['offset'])
            for k, (a, na, la, ha, b, nb, lb, hb) in enumerate(pairs):
                base[k] = max(base.get(k, 0.0), depth(obb(mats[a], la, ha), obb(mats[b], lb, hb)))
        worst = {}
        for f, (mats, _) in enumerate(frames):
            cache = {}

            def box(part, node, lo, hi):
                key = (part, node)
                if key not in cache:
                    cache[key] = obb(mats[part], lo, hi)
                return cache[key]
            for k, (a, na, la, ha, b, nb, lb, hb) in enumerate(pairs):
                d = depth(box(a, na, la, ha), box(b, nb, lb, hb))
                over = d-base[k]-self.tolerance
                if over > 0:
                    w = worst.setdefault((a, b), {'frames': set(), 'depth': 0.0})
                    w['frames'].add(f)
                    if d > w['depth']:
                        w.update(depth=d, frame=f, nodes=f'{a}/{na} and {b}/{nb}', allowed=base[k])
        for (a, b), w in sorted(worst.items(), key=lambda kv: -kv[1]['depth']):
            self.fail('parts', f'{a} and {b} pass into each other on frames {ranges(w["frames"])}: at worst '
                      f'{w["depth"]:.2f} m on frame {w["frame"]} ({w["nodes"]}; the rig\'s poses have them '
                      f'{w["allowed"]:.2f} m in, plus {self.tolerance:g}). Pose them apart, or "allow" '
                      f'[["{a}", "{b}"]] if it cannot be seen.',
                      parts=[a, b], frames=sorted(w['frames']), depth=round(w['depth'], 3), frame=w['frame'])
        self.checks['part_pairs'] = len(pairs)

    # ---- the floor, plants and slides

    def floor(self, frames):
        mv, rig = self.move, self.rig
        prox = rig.proxies()
        low = []
        sunk = {}
        feet = [p for p in ('foot_r', 'foot_l') if p in prox]
        foot_track = {p: [] for p in feet}
        for f, (mats, _) in enumerate(frames):
            lowest, who = math.inf, None
            lift = mv.root_travel(f)[1]          # the floor is this far below the root when motion lifts it
            for pid, px in prox.items():
                m = mats[pid]
                y = lift+min(m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2]+m[1][3] for v in px['points'])
                if y < lowest:
                    lowest, who = y, pid
                if y < -FLOOR_TOLERANCE and not mv.air:
                    s = sunk.setdefault(pid, {'frames': [], 'depth': 0.0})
                    s['frames'].append(f)
                    if -y > s['depth']:
                        s['depth'], s['frame'] = -y, f
            low.append(round(lowest, 3))
            travel = mv.root_travel(f)
            for p in feet:
                m = mats[p]
                pts = [apply(m, v) for v in prox[p]['points']]
                y = travel[1]+min(q[1] for q in pts)
                fx, _ = fight_xy((m[0][3], m[1][3], m[2][3]))
                foot_track[p].append((y, fx+travel[0]))
        for pid, s in sunk.items():
            if s['depth'] <= mv.floor_allow.get(pid, -1.0):
                self.warn('floor', f'{pid} goes {s["depth"]:.2f} m into the floor on frames {ranges(s["frames"])}: '
                          f'allowed ("floor_allow": up to {mv.floor_allow[pid]:g} m).',
                          part=pid, frames=s['frames'], depth=round(s['depth'], 3), frame=s['frame'])
                continue
            # what the pelvis needs on the worst frame: its offset's up raised by the depth (a key
            # there with "floor": true sets it)
            up = mv.pose_at(s['frame'])[1][1]
            self.fail('floor', f'{pid} goes {s["depth"]:.2f} m into the floor on frames {ranges(s["frames"])}: on frame '
                      f'{s["frame"]} the pelvis needs an offset up of {up+s["depth"]:.2f} (now {up:.2f}); a key there '
                      f'with "floor": true sets it.',
                      part=pid, frames=s['frames'], depth=round(s['depth'], 3), frame=s['frame'],
                      offset_up=round(up+s['depth'], 3))
        self.checks['lowest'] = min(low)
        for p, track in foot_track.items():
            slid = [f for f in range(1, len(track)) if track[f][0] < ON_FLOOR and track[f-1][0] < ON_FLOOR
                    and abs(track[f][1]-track[f-1][1]) > SLIDE]
            if slid:
                worst = max(abs(track[f][1]-track[f-1][1]) for f in slid)
                self.warn('slides', f'{p} slides along the floor on frames {ranges(slid)} (up to {worst:.2f} m a frame): '
                          f'"plant" it, or lift it.', part=p, frames=slid)
        # plants held
        for end, (top, mid, spans) in mv.plants.items():
            for a, b in spans:
                r, pos, t0 = mv._plant_target(end, a)
                missed = []
                for f in range(a, b+1):
                    m = frames[f][0][end]
                    t = mv.root_travel(f)
                    want_y, want_z = pos[1]-(t[1]-t0[1]), pos[2]+(t[0]-t0[0])
                    if math.hypot(m[1][3]-want_y, m[2][3]-want_z) > PLANT_TOLERANCE:
                        missed.append(f)
                if missed:
                    self.fail('floor', f'The plant of {end} on {a}-{b} cannot be held on frames {ranges(missed)}: '
                              f'the leg does not reach (lower the pelvis, or end the plant sooner).',
                              part=end, frames=missed)
        # steps: a foot on the floor
        steps = [f for f in range(mv.length) if mv.marks[f] & MARKS['step']]
        for f in steps:
            if feet and min(foot_track[p][f][0] for p in feet) > ON_FLOOR:
                self.warn('floor', f'A step mark on frame {f} with no foot on the floor.')


def verify(path, tolerance=0.12):
    """The report for one move file."""
    try:
        move = Move(path)
    except AnimError as error:
        return {'ok': False, 'move': str(path), 'verdict': 'format', 'failures': [
            {'check': 'format', 'path': error.path, 'message': str(error)}], 'warnings': []}
    c = Checker(move, tolerance)
    frames = []
    for f in range(move.length):
        mats = move.matrices(f)
        frames.append((mats, move.boxes_at(f, mats)))
    c.timing()
    c.boxes(frames)
    c.parts(frames)
    c.floor(frames)
    warnings = move.warnings+c.warnings
    return {'ok': not c.failures, 'move': str(path), 'name': move.name, 'rig': move.rig.name,
            'verdict': 'pass' if not c.failures else ', '.join(sorted({f['check'] for f in c.failures})),
            'length': move.length, 'keys': [k[0] for k in move.pose_keys], 'phases': move.phases,
            'failures': c.failures, 'warnings': warnings, 'checks': c.checks}
