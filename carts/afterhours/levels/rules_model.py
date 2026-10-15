"""A model of After Hours' stealth rules in floating point, for designing rooms' puzzles and drafting
their solution tapes (the rooms' and levels' solutions.py). It follows agent A's runtime
(carts/afterhours/dr_*.akr: dr_train, dr_watch, dr_sight, dr_thief, dr_game's tick) step for step, but
the runtime is the truth: a tape drafted here is checked in the cart, where 16.16 fixed point moves
the thief a few centimetres from this model over a run. When A changes a rule, change it here too
and redraft the tapes.

Rules as of the level 1 changes (DESIGN.md, Decided, 2026-10-15), set by RULES below:
  centre  caught only when a cone covers the thief's centre (Gate 1: any part of his footprint)
  doors   a stopped train's cars block cones except through their open doors' gaps (Gate 1: the
          whole car blocked)

Stage 2's doors and keycards (afterhours.game.mochi, `door` and `keycard`; NOTES_B.md): a room
is entered by a door (Sim's `door`: the door he comes in by, at its spawn), holding the run's
cards (`held`) with the run's doors opened (`opened`). A card is picked up within 0.5 m of his
centre; a shut staff door is a wall (solid, blocking) until he walks into it holding its colour;
he goes through a door with `to` or `end` when his centre is in its box. Sim.left_by is the door
he left by.
"""
import json
import math
from pathlib import Path

RULES = {'centre': True, 'doors': True}

THIEF_R = 0.3
WALK = 0.04
RUN = 0.08
GUARD_R = 0.3
TURN_RATE = 0.0698
NOISE_PACE = 1.5
LOOK_TICKS = 150
LOOK_SWING = 1.2217
STUCK_TICKS = 40
NEAR_NOISE = 0.8
TOY_R = 0.12
TOY_SPEED = 0.015
TOY_TICKS = 480
TOY_NOISE = 4.0
BELL_DELAY = 180
BELL_NOISE = 9.0
RAYS = 17
SHELL = 0.12
DEG = math.pi / 180
TAU = 2 * math.pi

UP, DOWN, LEFT, RIGHT, A, B, X, Y, L, R = (1 << i for i in range(10))


def wrap(a):
    while a > math.pi: a -= TAU
    while a < -math.pi: a += TAU
    return a


TURN_TIE = 0.001


def turn_toward(h, want, step):
    d = wrap(want - h)
    if abs(d) >= math.pi - TURN_TIE:    # exactly round: to his right, clockwise from above (A's rule 5)
        d = abs(d)
    return wrap(h + max(-step, min(step, d)))


def heading_to(dx, dz):
    return math.atan2(dx, dz)


class Box:
    def __init__(self, cx, cz, sx, sz, blocks=True, solid=True, edge=False, yaw=0.0):
        self.cx, self.cz, self.hx, self.hz = cx, cz, sx / 2, sz / 2
        self.c, self.s = math.cos(yaw), math.sin(yaw)
        self.blocks, self.solid, self.edge = blocks, solid, edge

    def local(self, x, z):
        dx, dz = x - self.cx, z - self.cz
        return dx * self.c - dz * self.s, dx * self.s + dz * self.c

    def contains(self, x, z):
        lx, lz = self.local(x, z)
        return abs(lx) <= self.hx and abs(lz) <= self.hz

    def push(self, x, z, r):
        lx, lz = self.local(x, z)
        if abs(lx) >= self.hx + r or abs(lz) >= self.hz + r:
            return x, z, False
        qx = max(-self.hx, min(self.hx, lx))
        qz = max(-self.hz, min(self.hz, lz))
        dx, dz = lx - qx, lz - qz
        d2 = dx * dx + dz * dz
        if d2 >= r * r:
            return x, z, False
        if d2 > 0.0001:
            d = math.sqrt(d2)
            k = (r - d) / d
            lx += dx * k
            lz += dz * k
        else:
            px, pz = self.hx - abs(lx), self.hz - abs(lz)
            if px < pz:
                lx = -self.hx - r if lx < 0 else self.hx + r
            else:
                lz = -self.hz - r if lz < 0 else self.hz + r
        return self.cx + lx * self.c + lz * self.s, self.cz - lx * self.s + lz * self.c, True

    def corners(self):
        out = []
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, lz = self.hx * sx, self.hz * sz
            out.append((self.cx + lx * self.c + lz * self.s, self.cz - lx * self.s + lz * self.c))
        return out


def segs_of(corners):
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


class Train:
    def __init__(self, p, path):
        self.__dict__.update(p)
        self.pts = path
        (x0, _, z0), (x1, _, z1) = path[0], path[-1]
        self.L = math.hypot(x1 - x0, z1 - z0)
        self.ux, self.uz = (x1 - x0) / self.L, (z1 - z0) / self.L
        self.x0, self.z0 = x0, z0
        self.left = self.sides in ('left', 'both')
        self.right = self.sides in ('right', 'both')
        self.length = self.car_length * self.cars

    def state(self, t):
        k = (t - self.offset) // self.period
        tau = t - self.offset - k * self.period
        if tau < self.arrive:
            u = tau / self.arrive
            v = 1 - u
            return 'arr', self.stop - self.stop * v * v, False, False
        if tau < self.arrive + self.dwell:
            return 'stop', self.stop, True, tau == self.arrive + self.dwell - 1
        if tau < self.arrive + self.dwell + self.leave:
            u = (tau - self.arrive - self.dwell) / self.leave
            return 'leave', self.stop + (self.L + self.length - self.stop) * u * u, False, False
        return 'off', 0.0, False, False

    def cars_at(self, head):
        out = []
        for c in range(self.cars):
            front = min(head - self.car_length * c, self.L)
            back = max(head - self.car_length * (c + 1), 0.0)
            if front <= back + 0.01:
                continue
            mid = (front + back) / 2
            out.append(dict(cx=self.x0 + self.ux * mid, cz=self.z0 + self.uz * mid, len=front - back,
                            whole=front - back >= self.car_length - 0.01))
        return out

    def car_box(self, c, a0, a1, b0, b1):
        ma, mb = (a0 + a1) / 2, (b0 + b1) / 2
        # local x along u, local z along the left (-uz, ux): box c = ux, s = -uz
        bx = Box(c['cx'] + self.ux * ma - self.uz * mb, c['cz'] + self.uz * ma + self.ux * mb, a1 - a0, b1 - b0,
                 blocks=False, solid=True)
        bx.c, bx.s = self.ux, -self.uz
        return bx

    def door_mid(self, length, k):
        return length / 2 - (length * (2 * (self.doors - 1 - k) + 1)) / (2 * self.doors)


CARD_R = 0.5
DOOR_REACH = 0.38      # THIEF_R + 0.08: a shut door opens before he touches it


class Sim:
    def __init__(self, play=None, world=None, room=None, override=None, door=None, held=(), opened=()):
        """play: a room's play file (dict or path); or world: a world recipe (path), with room the
        id of the room entity whose box selects the entities (default: every entity of the first
        cell)."""
        if play is not None:
            if not isinstance(play, dict):
                play = json.loads(Path(play).read_text())
            ents_l, paths = play['entities'], play.get('paths', {})
        else:
            w = json.loads(Path(world).read_text())
            cells = w.get('cells') or []
            ents_l = [e for c in cells for e in c.get('entities', [])]
            paths = w.get('paths', {})
            if room:
                rm = next(e for e in ents_l if e['id'] == room)
                cx, cz = rm['position'][0], rm['position'][2]
                hx, hz = rm['params']['size'][0] / 2, rm['params']['size'][2] / 2
                ents_l = [e for e in ents_l if abs(e['position'][0] - cx) <= hx and abs(e['position'][2] - cz) <= hz]
        ents = {e['id']: json.loads(json.dumps(e)) for e in ents_l}
        if override:
            for k, v in override.items():
                ents[k]['params'].update(v)
        self.ents = ents
        self.walls = []
        for e in ents.values():
            if e['type'] == 'wall':
                p = e['params']
                self.walls.append(Box(e['position'][0], e['position'][2], p['size'][0], p['size'][2],
                                      p.get('blocks', True), p.get('solid', True)))
        self.trains = []
        for e in ents.values():
            if e['type'] == 'train':
                p = dict(e['params'])
                t = Train(p, paths[p['path']]['points'])
                self.trains.append(t)
                # the track band's two sides: thin edge strips just inside it (as A's stand-in)
                cx = t.x0 + t.ux * t.L / 2
                cz = t.z0 + t.uz * t.L / 2
                for sgn in (-1, 1):
                    self.walls.append(Box(cx, cz + sgn * (t.width / 2 - 0.1), t.L, 0.2, blocks=False, solid=True, edge=True))
        self.segs = []
        for b in self.walls:
            if b.blocks:
                self.segs += segs_of(b.corners())
        room = next(e for e in ents.values() if e['type'] == 'room')
        sp = ents[room['params']['entry']]
        if door is not None:
            sp = ents[ents[door]['params']['spawn']]
        self.came_by = door
        self.spawn = (sp['position'][0], sp['position'][2], sp['params'].get('yaw', 0) * DEG)
        ex = ents.get(room['params'].get('exit'))
        self.exit = None if ex is None else Box(ex['position'][0], ex['position'][2], ex['params']['size'][0], ex['params']['size'][2])
        # stage 2: the doors (in entity order, A's door index) and the keycards
        self.doors = []
        for e in ents.values():
            if e['type'] != 'door':
                continue
            p = e['params']
            sz = p.get('size', [1.2, 2.2, 0.4])
            self.doors.append(dict(id=e['id'], card=p.get('card', 'none'), to=p.get('to'), end=p.get('end', False),
                                   box=Box(e['position'][0], e['position'][2], sz[0], sz[2], yaw=e.get('yaw', 0) * DEG)))
        self.cards = [dict(id=e['id'], colour=e['params']['colour'], x=e['position'][0], z=e['position'][2])
                      for e in ents.values() if e['type'] == 'keycard']
        self.run_held, self.run_opened = set(held), set(opened)
        self.base_segs = self.segs
        self.ntoys = room['params'].get('toys', 0)
        self.nbells = room['params'].get('bells', 0)
        self.spots = [Box(e['position'][0], e['position'][2], e['params']['size'][0], e['params']['size'][2])
                      for e in ents.values() if e['type'] == 'hide_spot']
        self.frag = [(e['position'][0], e['position'][2], e['params'].get('radius', 0.4), e['params'].get('noise', 8))
                     for e in ents.values() if e['type'] == 'fragile']
        self.wp_index = {}
        self.wps = []
        for e in ents.values():
            if e['type'] == 'waypoint':
                self.wp_index[e['id']] = len(self.wps)
                self.wps.append(e)
        self.wps = [dict(x=e['position'][0], z=e['position'][2], next=e['params'].get('next'),
                         wait=e['params'].get('wait', 0), look=e['params'].get('look', 0) * DEG) for e in self.wps]
        for wp in self.wps:
            wp['next'] = self.wp_index.get(wp['next'], -1) if wp['next'] else -1
        self.watch = []
        for e in ents.values():
            if e['type'] != 'guard':
                continue
            p = e['params']
            d = dict(id=e['id'], kind=p['kind'], x=e['position'][0], z=e['position'][2],
                     route=self.wp_index.get(p.get('route'), -1) if p.get('route') else -1,
                     sight=p.get('sight', 6), half=p.get('fov', 60) * DEG / 2, speed=p.get('speed', 1.2) / 60,
                     look_a=p.get('look_a', 0) * DEG, look_b=p.get('look_b', 0) * DEG, hold=p.get('hold', 60),
                     turn=p.get('turn', 90), phase=p.get('phase', 0), hear=p.get('hear', 6),
                     turn_rate=p.get('turn_rate', 240) * DEG / 60)
            d['head'] = e.get('yaw', 0) * DEG     # A's dr_world: the entity's yaw
            self.watch.append(d)
        self.reset()

    # ---- stage 2's doors
    def door_shut(self, d):
        return d['card'] != 'none' and d['id'] not in self.opened

    def doors_update(self):
        """The shut doors into the wall map (solid and blocking)."""
        self.shut = [d['box'] for d in self.doors if self.door_shut(d)]
        self.segs = list(self.base_segs)
        for b in self.shut:
            self.segs += segs_of(b.corners())

    # ---- state
    def reset(self):
        self.held = set(self.run_held)        # the room as it was when he came in
        self.opened = set(self.run_opened)
        self.cards_here = [c for c in self.cards if c['colour'] not in self.run_held]
        self.taken = set()
        self.left_by = None
        self.doors_update()
        x, z, h = self.spawn
        self.th = dict(x=x, z=z, head=h, hidden=False, toys=self.ntoys, bells=self.nbells, tool='toy' if self.ntoys else 'bell',
                       car=None)
        self.toys = []
        self.bells = []
        self.frag_down = [False] * len(self.frag)
        self.guards = []
        for d in self.watch:
            g = dict(x=d['x'], z=d['z'], head=d['head'], target=d['route'], toy=None, away=False, timer=0)
            if d['kind'] == 'patrol':
                g['mode'] = 'route' if d['route'] >= 0 else 'hold'
            else:
                g['mode'] = 'posted'
                g['head'] = self.posted_head(d, 0)
            self.guards.append(g)
        self.clock = 0
        self.prev = 0
        self.trains_update(0)
        self.sight()

    def posted_head(self, d, t):
        cycle = 2 * (d['hold'] + d['turn'])
        p = (t + d['phase']) % cycle
        if p < d['hold']: return d['look_a']
        p -= d['hold']
        if p < d['turn']: return d['look_a'] + (d['look_b'] - d['look_a']) * p / d['turn']
        p -= d['turn']
        if p < d['hold']: return d['look_b']
        p -= d['hold']
        return d['look_b'] + (d['look_a'] - d['look_b']) * p / d['turn']

    def trains_update(self, t):
        self.dyn_segs = []
        self.dyn_boxes = []
        self.tstate = []
        for tr in self.trains:
            phase, head, opn, closing = tr.state(t)
            cars = tr.cars_at(head) if phase != 'off' else []
            self.tstate.append(dict(phase=phase, head=head, open=opn, closing=closing, cars=cars))
            hw = tr.width / 2
            if not RULES['doors']:
                for c in cars:
                    b = tr.car_box(c, -c['len'] / 2, c['len'] / 2, -hw, hw)
                    self.dyn_segs += segs_of(b.corners())
            else:
                # dr_train.akr's train_sight(): each car's two side lines, with a gap at each open
                # door (stopped, doors on that side, the car whole on the path), and the train's
                # two ends; nothing between its cars
                def seg(c, a0, b0, a1, b1):
                    p0 = (c['cx'] + tr.ux * a0 - tr.uz * b0, c['cz'] + tr.uz * a0 + tr.ux * b0)
                    p1 = (c['cx'] + tr.ux * a1 - tr.uz * b1, c['cz'] + tr.uz * a1 + tr.ux * b1)
                    self.dyn_segs.append((p0, p1))
                for c in cars:
                    hl = c['len'] / 2
                    for left in (False, True):
                        b = hw if left else -hw
                        sd = tr.left if left else tr.right
                        if not opn or not sd or not c['whole']:
                            seg(c, -hl, b, hl, b)
                            continue
                        frm = -hl
                        for k in range(tr.doors):
                            mid = tr.door_mid(c['len'], k)
                            g0 = mid - tr.door_width / 2
                            if g0 > frm: seg(c, frm, b, g0, b)
                            frm = mid + tr.door_width / 2
                        if hl > frm: seg(c, frm, b, hl, b)
                if cars:
                    h, e = cars[0], cars[-1]
                    seg(h, h['len'] / 2, -hw, h['len'] / 2, hw)
                    seg(e, -e['len'] / 2, -hw, -e['len'] / 2, hw)
            if opn:
                n0 = len(self.dyn_boxes)
                for c in cars:
                    hl = c['len'] / 2
                    for left in (False, True):
                        b0, b1 = (hw - SHELL, hw) if left else (-hw, -hw + SHELL)
                        sd = tr.left if left else tr.right
                        if not sd or not c['whole']:
                            self.dyn_boxes.append(tr.car_box(c, -hl, hl, b0, b1))
                            continue
                        frm = -hl
                        for k in range(tr.doors):
                            mid = tr.door_mid(c['len'], k)
                            g0 = mid - tr.door_width / 2
                            if g0 > frm: self.dyn_boxes.append(tr.car_box(c, frm, g0, b0, b1))
                            frm = mid + tr.door_width / 2
                        if hl > frm: self.dyn_boxes.append(tr.car_box(c, frm, hl, b0, b1))
                if cars:
                    h = cars[0]
                    if h['whole']: self.dyn_boxes.append(tr.car_box(h, h['len'] / 2 - SHELL, h['len'] / 2, -hw, hw))
                    e = cars[-1]
                    if e['whole']: self.dyn_boxes.append(tr.car_box(e, -e['len'] / 2, -e['len'] / 2 + SHELL, -hw, hw))

    def keys_update(self):
        """A's keys_update(), after the thief's move: cards (strictly within CARD_R of his centre),
        then shut doors of a colour he holds that his centre comes strictly within DOOR_REACH of:
        open from this tick (cones too), passable from the next."""
        th = self.th
        for c in self.cards_here:
            if c['id'] not in self.taken and (th['x'] - c['x']) ** 2 + (th['z'] - c['z']) ** 2 < CARD_R * CARD_R:
                self.taken.add(c['id'])
                self.held.add(c['colour'])
        opened = False
        for d in self.doors:
            if self.door_shut(d) and d['card'] in self.held and d['box'].push(th['x'], th['z'], DOOR_REACH)[2]:
                self.opened.add(d['id'])
                if d['to']:
                    self.opened.add(d['to'])
                opened = True
        if opened:
            self.doors_update()

    def door_passage(self, x, z):
        for tr, st in zip(self.trains, self.tstate):
            if not st['open']: continue
            hw = tr.width / 2
            for c in st['cars']:
                if not c['whole']: continue
                dx, dz = x - c['cx'], z - c['cz']
                a = dx * tr.ux + dz * tr.uz
                b = -dx * tr.uz + dz * tr.ux
                if b > 0 and not tr.left: continue
                if b < 0 and not tr.right: continue
                if abs(b) > hw + 1.0: continue
                for k in range(tr.doors):
                    if abs(a - tr.door_mid(c['len'], k)) <= tr.door_width / 2: return True
        return False

    def train_inside(self, x, z):
        for i, (tr, st) in enumerate(zip(self.trains, self.tstate)):
            for c in st['cars']:
                dx, dz = x - c['cx'], z - c['cz']
                a = dx * tr.ux + dz * tr.uz
                b = -dx * tr.uz + dz * tr.ux
                if abs(a) <= c['len'] / 2 and abs(b) <= tr.width / 2: return i
        return None

    def solid_push(self, x, z, r):
        for _ in range(3):
            hit = False
            through = bool(self.dyn_boxes) and self.door_passage(x, z)
            for b in self.walls:
                if b.solid and not (b.edge and through):
                    x, z, h = b.push(x, z, r)
                    hit |= h
            for b in self.shut:
                x, z, h = b.push(x, z, r)
                hit |= h
            for b in self.dyn_boxes:
                x, z, h = b.push(x, z, r)
                hit |= h
            if not hit: break
        return x, z

    # ---- a tick
    def tick(self, pad, sx, sy):
        press = pad & ~self.prev
        self.prev = pad
        self.noises = []
        t = self.clock
        self.trains_update(t)
        self.thief_update(pad, press, sx, sy, t)
        self.tools_update(t)
        for d, g in zip(self.watch, self.guards):
            self.guard_update(d, g, t)
        self.sight()
        why = None
        th = self.th
        for i, (d, g) in enumerate(zip(self.watch, self.guards)):
            if not th['hidden'] and fan_hits(g['fan'], th['x'], th['z'], 0.0 if RULES['centre'] else THIEF_R):
                why = ('seen', d['id']); break
            if d['kind'] != 'camera' and (th['x'] - g['x']) ** 2 + (th['z'] - g['z']) ** 2 < (THIEF_R + GUARD_R) ** 2:
                why = ('touched', d['id']); break
        if why is None and th['car'] is not None and self.tstate[th['car']]['closing']:
            why = ('doors', th['car'])
        cleared = why is None and self.exit is not None and self.exit.contains(th['x'], th['z'])
        if why is None and not cleared:
            for d in self.doors:
                if (d['to'] or d['end']) and not self.door_shut(d) and d['box'].contains(th['x'], th['z']):
                    cleared = True
                    self.left_by = d['id']
                    break
        self.clock += 1
        return why, cleared

    def thief_update(self, pad, press, sx, sy, t):
        th = self.th
        mx = mz = 0.0
        if pad & LEFT: mx -= 1
        if pad & RIGHT: mx += 1
        if pad & UP: mz += 1
        if pad & DOWN: mz -= 1
        if mx and mz:
            mx *= 0.70711; mz *= 0.70711
        # the harness hands the stick over as s/127 and the game quantizes it again: |s| - 1
        q = lambda v: 0 if v == 0 or abs(v) >= 127 and False else (v if abs(v) >= 127 else (v - 1 if v > 0 else v + 1))
        sx, sy = q(sx), q(sy)
        if mx == 0 and mz == 0 and (sx or sy):
            fx, fz = sx / 127, sy / 127
            m2 = fx * fx + fz * fz
            if m2 > 0.04:
                m = math.sqrt(m2)
                k = min(m, 1) / m
                mx, mz = fx * k, fz * k
        moving = mx != 0 or mz != 0
        if th['hidden']:
            if moving or press & A: th['hidden'] = False
            return
        running = False
        if moving:
            step = WALK
            if pad & R:
                step = RUN; running = True
            th['head'] = heading_to(mx, mz)
            th['x'], th['z'] = self.solid_push(th['x'] + mx * step, th['z'] + mz * step, THIEF_R)
        th['car'] = self.train_inside(th['x'], th['z'])
        self.keys_update()
        if running: self.noises.append((th['x'], th['z'], 0.0, None))
        for i, (fx, fz, fr, fn) in enumerate(self.frag):
            if self.frag_down[i]: continue
            rr = fr + THIEF_R
            if (th['x'] - fx) ** 2 + (th['z'] - fz) ** 2 < rr * rr:
                self.frag_down[i] = t
                self.noises.append((fx, fz, fn, None))
        if press & A:
            for s in self.spots:
                if s.contains(th['x'], th['z']):
                    th['hidden'] = True; break
        if press & L:
            th['tool'] = 'bell' if th['tool'] == 'toy' else 'toy'
        if press & B:
            if th['tool'] == 'toy' and th['toys'] > 0:
                x, z = self.solid_push(th['x'] + math.sin(th['head']) * 0.5, th['z'] + math.cos(th['head']) * 0.5, TOY_R)
                self.toys.append(dict(x=x, z=z, head=th['head'], ticks=TOY_TICKS))
                th['toys'] -= 1
            elif th['tool'] == 'bell' and th['bells'] > 0:
                self.bells.append(dict(x=th['x'], z=th['z'], ticks=BELL_DELAY))
                th['bells'] -= 1

    def tools_update(self, t):
        for i, y in enumerate(self.toys):
            if y['ticks'] <= 0: continue
            y['ticks'] -= 1
            nx = y['x'] + math.sin(y['head']) * TOY_SPEED
            nz = y['z'] + math.cos(y['head']) * TOY_SPEED
            px, pz = self.solid_push(nx, nz, TOY_R)
            if abs(px - nx) > 0.001 or abs(pz - nz) > 0.001:
                y['head'] = wrap(y['head'] + math.pi / 2)
            else:
                y['x'], y['z'] = nx, nz
            self.noises.append((y['x'], y['z'], TOY_NOISE, i))
        for b in self.bells:
            if b['ticks'] < 0: continue
            b['ticks'] -= 1
            if b['ticks'] <= 0:
                b['ticks'] = -1
                self.noises.append((b['x'], b['z'], BELL_NOISE, None))

    def guard_walk(self, g, tx, tz, step, stop):
        # g['rate'] is set by guard_update from the watcher's turn_rate
        dx, dz = tx - g['x'], tz - g['z']
        d2 = dx * dx + dz * dz
        if d2 <= stop * stop + step * step / 4:
            if stop == 0:
                g['x'], g['z'] = tx, tz
            return True
        d = math.sqrt(d2)
        k = min(step, d - stop) / d
        x, z = g['x'] + dx * k, g['z'] + dz * k
        g['head'] = turn_toward(g['head'], heading_to(dx, dz), g['rate'])
        for _ in range(2):
            for b in self.walls:
                if b.solid:
                    x, z, _h = b.push(x, z, GUARD_R)
        g['x'], g['z'] = x, z
        return False

    def guard_progress(self, g, tx, tz):
        d = (g['x'] - tx) ** 2 + (g['z'] - tz) ** 2
        if d < g['best'] - 0.01:
            g['best'] = d; g['stuck'] = 0; return True
        g['stuck'] += 1
        return g['stuck'] < STUCK_TICKS

    def guard_update(self, d, g, t):
        if d['kind'] != 'camera':
            for (nx, nz, r, toy) in self.noises:
                if r == 0: r = d['hear']
                if (g['x'] - nx) ** 2 + (g['z'] - nz) ** 2 > r * r: continue
                if toy is not None and g['toy'] == toy and g['mode'] == 'go': continue
                if not g['away']:
                    g['away'] = True
                    g['b'] = (g['x'], g['z'], g['mode'], g['target'], g['timer'])
                g['mode'] = 'go'; g['nx'], g['nz'] = nx, nz; g['toy'] = toy; g['stuck'] = 0; g['best'] = 30000.0
        g['rate'] = d['turn_rate']
        pace = d['speed'] * NOISE_PACE
        m = g['mode']
        if m == 'route':
            w = self.wps[g['target']]
            if self.guard_walk(g, w['x'], w['z'], d['speed'], 0.0):
                if w['wait'] > 0:
                    g['mode'] = 'wait'; g['timer'] = w['wait']
                elif w['next'] >= 0:
                    g['target'] = w['next']
                else:
                    g['mode'] = 'hold'
        elif m == 'wait':
            w = self.wps[g['target']]
            g['head'] = turn_toward(g['head'], w['look'], d['turn_rate'])
            g['timer'] -= 1
            if g['timer'] <= 0:
                if w['next'] >= 0:
                    g['target'] = w['next']; g['mode'] = 'route'
                else:
                    g['mode'] = 'hold'
        elif m == 'hold':
            if g['target'] >= 0: g['head'] = turn_toward(g['head'], self.wps[g['target']]['look'], d['turn_rate'])
        elif m == 'posted':
            g['head'] = self.posted_head(d, t)
        elif m == 'resume':
            want = self.posted_head(d, t)
            g['head'] = turn_toward(g['head'], want, d['turn_rate'])
            if abs(wrap(want - g['head'])) < d['turn_rate'] * 2: g['mode'] = 'posted'
        elif m == 'go':
            if g['toy'] is not None and self.toys[g['toy']]['ticks'] > 0:
                g['nx'], g['nz'] = self.toys[g['toy']]['x'], self.toys[g['toy']]['z']
            there = self.guard_walk(g, g['nx'], g['nz'], pace, NEAR_NOISE)
            if there:
                g['head'] = turn_toward(g['head'], heading_to(g['nx'] - g['x'], g['nz'] - g['z']), d['turn_rate'])
            following = g['toy'] is not None and self.toys[g['toy']]['ticks'] > 0
            if (there and not following) or (not there and not self.guard_progress(g, g['nx'], g['nz'])):
                g['mode'] = 'look'; g['timer'] = LOOK_TICKS; g['look_base'] = g['head']; g['toy'] = None
        elif m == 'look':
            g['timer'] -= 1
            u = LOOK_TICKS - g['timer']
            g['head'] = wrap(g['look_base'] + LOOK_SWING * math.sin(TAU * u / (LOOK_TICKS / 2)))
            if g['timer'] <= 0:
                g['mode'] = 'back'; g['stuck'] = 0; g['best'] = 30000.0
        elif m == 'back':
            bx, bz, bm, bt, btm = g['b']
            if self.guard_walk(g, bx, bz, d['speed'], 0.0) or not self.guard_progress(g, bx, bz):
                g['away'] = False; g['mode'] = bm; g['target'] = bt; g['timer'] = btm
                if g['mode'] == 'posted': g['mode'] = 'resume'

    def sight(self):
        segs = self.segs + self.dyn_segs
        for d, g in zip(self.watch, self.guards):
            g['fan'] = fan_cast(g['x'], g['z'], g['head'], d['half'], d['sight'], segs)


def ray_seg(ax, az, dx, dz, s, best):
    (sax, saz), (sbx, sbz) = s
    ex, ez = sbx - sax, sbz - saz
    den = dx * ez - dz * ex
    if abs(den) < 0.0005: return best
    wx, wz = sax - ax, saz - az
    tn = wx * ez - wz * ex
    un = wx * dz - wz * dx
    if den > 0:
        if tn < 0 or un < 0 or un > den: return best
    else:
        if tn > 0 or un > 0 or un < den: return best
    t = tn / den
    return t if t < best else best


def fan_cast(ax, az, head, half, rng, segs):
    near = [s for s in segs if not (max(s[0][0], s[1][0]) < ax - rng or min(s[0][0], s[1][0]) > ax + rng or
                                    max(s[0][1], s[1][1]) < az - rng or min(s[0][1], s[1][1]) > az + rng)]
    pts = []
    for k in range(RAYS):
        a = head - half + (half * 2 * k) / (RAYS - 1)
        dx, dz = math.sin(a) * rng, math.cos(a) * rng
        t = 1.0
        for s in near:
            t = ray_seg(ax, az, dx, dz, s, t)
        pts.append((ax + dx * t, az + dz * t))
    return (ax, az, pts)


def cross3(ox, oz, ax, az, bx, bz):
    return (ax - ox) * (bz - oz) - (az - oz) * (bx - ox)


def seg_dist(ax, az, bx, bz, x, z):
    ex, ez = bx - ax, bz - az
    ee = ex * ex + ez * ez
    t = 0 if ee == 0 else max(0, min(1, ((x - ax) * ex + (z - az) * ez) / ee))
    return math.hypot(x - ax - ex * t, z - az - ez * t)


def fan_hits(fan, x, z, r):
    ax, az, p = fan
    for k in range(RAYS - 1):
        c0 = cross3(ax, az, p[k][0], p[k][1], x, z)
        c1 = cross3(ax, az, p[k + 1][0], p[k + 1][1], x, z)
        if c0 <= 0 and c1 >= 0:
            if cross3(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], x, z) <= 0: return True
    if seg_dist(ax, az, p[0][0], p[0][1], x, z) < r: return True
    if seg_dist(ax, az, p[-1][0], p[-1][1], x, z) < r: return True
    for k in range(RAYS - 1):
        if seg_dist(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], x, z) < r: return True
    return False


def fan_dist(fan, x, z):
    """How far (x, z) is from the fan's polygon (0 inside)."""
    ax, az, p = fan
    for k in range(RAYS - 1):
        c0 = cross3(ax, az, p[k][0], p[k][1], x, z)
        c1 = cross3(ax, az, p[k + 1][0], p[k + 1][1], x, z)
        if c0 <= 0 and c1 >= 0 and cross3(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], x, z) <= 0: return 0.0
    best = min(seg_dist(ax, az, p[0][0], p[0][1], x, z), seg_dist(ax, az, p[-1][0], p[-1][1], x, z))
    for k in range(RAYS - 1):
        best = min(best, seg_dist(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], x, z))
    return best
