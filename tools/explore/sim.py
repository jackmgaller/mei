"""Flying the robot over the column world, many take-offs at once (numpy).

One tick here is one of player.akr's: the same order of updates (the glider at the apex, the
stick's air control, gravity or the glider's easing, the horizontal move against walls, the
vertical move, the head at ceilings, the feet onto floors), then attach.akr's grabs (poles and
rails, from the plain air states only). Differences from the controller, all on purpose:

- walls are the column grid's (world.py): a body whose feet are at y over a column is pushed if
  the column's wall intervals hold y. A move into a wall is cut to its part along the wall
  (a slide), or dropped; the wall's normal is the one the interval keeps;
- the ledge test is ledge_top()'s on the column grid: the highest floor within T.LedgeHigh above
  the feet just beyond the wall, at least T.LedgeLow above them, gentle (normal y >= 0.8) and with
  room to stand;
- a wall slide (a wall upright enough, met fast enough) is recorded as a kick chance (the later
  pass takes it) and the body then drops down the wall;
- the crack bridge (wp_floor_across) is not used: the grid's columns are 0.25 m apart.

Outcomes: LAND (a floor), LEDGE (a ledge grab, then the climb onto it), POLE, RAIL (a grind), HANG,
OUT (left the level's frame), FELL (fell below every floor: through the world), TIMEOUT.
"""
from dataclasses import dataclass, field
import math

import numpy as np

from .moves import AIR, GLIDE, DIVE, ST_DOUBLE, ST_THIRD

LAND, LEDGE, POLE, RAIL, HANG, OUT, FELL, TIMEOUT = range(1, 9)
OUTCOME_NAMES = {0: 'flying', LAND: 'land', LEDGE: 'ledge', POLE: 'pole', RAIL: 'grind', HANG: 'hang', OUT: 'out',
                 FELL: 'fell', TIMEOUT: 'timeout'}


@dataclass
class Batch:
    """Take-offs: one row each. Angles in radians (0: +z, pi/2: +x); speeds per tick."""
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    yaw: np.ndarray
    vy: np.ndarray
    fwd: np.ndarray
    ctrl: np.ndarray
    cap: np.ndarray
    stick: np.ndarray
    st: np.ndarray              # moves.ST_*
    glide: np.ndarray           # armed: the glider at the apex
    dive: np.ndarray            # dive at the apex
    state: np.ndarray = None    # AIR / GLIDE / DIVE at the start
    skip_pole: np.ndarray = None   # a pole index not grabbed (just left), or -1
    skip_rail: np.ndarray = None
    max_ticks: int = 600

    def __len__(self):
        return len(self.x)

    @staticmethod
    def concat(batches):
        bs = [b for b in batches if len(b)]
        if not bs:
            return empty_batch()
        out = {}
        for f in ('x', 'y', 'z', 'yaw', 'vy', 'fwd', 'ctrl', 'cap', 'stick', 'st', 'glide', 'dive', 'state',
                  'skip_pole', 'skip_rail'):
            out[f] = np.concatenate([b.filled(f) for b in bs])
        return Batch(**out, max_ticks=max(b.max_ticks for b in bs))

    def filled(self, f):
        v = getattr(self, f)
        if v is None:
            n = len(self.x)
            return np.zeros(n, np.int8) if f == 'state' else np.full(n, -1, np.int64)
        return v

    def take(self, idx):
        out = {}
        for f in ('x', 'y', 'z', 'yaw', 'vy', 'fwd', 'ctrl', 'cap', 'stick', 'st', 'glide', 'dive', 'state',
                  'skip_pole', 'skip_rail'):
            out[f] = self.filled(f)[idx]
        return Batch(**out, max_ticks=self.max_ticks)


def empty_batch():
    z = np.zeros(0)
    return Batch(z, z, z, z, z, z, z, z, z, z.astype(np.int8), z.astype(bool), z.astype(bool),
                 z.astype(np.int8), z.astype(np.int64), z.astype(np.int64))


@dataclass
class Result:
    outcome: np.ndarray         # per take-off
    x: np.ndarray               # where it ended (a ledge: the ledge's point; a grab: the body)
    y: np.ndarray
    z: np.ndarray
    ticks: np.ndarray
    floor: np.ndarray           # LAND / LEDGE: the floor entry; POLE / RAIL / HANG: the thing's index
    rail_s: np.ndarray          # RAIL / HANG: how far along the path; POLE: the angle round it
    rail_v: np.ndarray          # RAIL: signed speed along the path (per tick)
    max_y: np.ndarray
    hole_x: np.ndarray          # where it first flew over a column with no floor under the feet
    hole_z: np.ndarray          # (inside the frame), NaN if never
    out_x: np.ndarray           # where it crossed out of the frame
    out_z: np.ndarray
    out_y: np.ndarray
    glided: np.ndarray
    kicks: dict = field(default_factory=dict)       # arrays: i, tick, x, y, z, yaw_in, speed, nx, nz
    releases: dict = field(default_factory=dict)    # arrays: i, tick, x, y, z, yaw, fwd, vy
    pickups: dict = field(default_factory=dict)     # arrays: i, entity, tick, state
    trace: list = None                              # per take-off: [(x, y, z, state)] when asked


class Flyer:
    """The world's grids for flying: the model, the poles, the rails and the pickups."""

    def __init__(self, model, tuning, poles=(), rails=(), pickups=()):
        self.m = model
        self.tn = tuning
        tn = tuning
        self.G = tn.mps2('Gravity')
        self.FALL = tn.mps('FallMax')
        self.AIRACC = tn.mps2('AirAccel')
        self.AIRMAX = tn.mps('AirMax')
        self.AIRDRAG = tn.mps2('AirDrag')
        self.GS = tn.mps('GlideSpeed')
        self.SINK = tn.mps('GlideSink')
        self.GE = tn.rps('GlideEase')
        self.DIVEB = tn.mps('DiveBoost')
        self.DIVEMAX = tn.mps('DiveMax')
        self.DIVEVY = tn.mps('DiveVy')
        self.LLOW = tn.t['LedgeLow']
        self.LHIGH = tn.t['LedgeHigh']
        self.KTILT = math.sin(math.radians(tn.t['KickTilt']))
        self.KMIN = tn.mps('KickMinSpeed')
        self.R = tn.radius
        self.H = tn.height
        self.STEP = tn.step
        self.PREACH = tn.t['PoleReach']
        self.PTOP = tn.t['PoleTop']
        self.RREACH = tn.t['RailReach']
        f = model.floors
        self.ymin = (float(f.y.min()) if len(f) else 0.0) - 6.0
        # poles: (x, y base, z, top, front, ang), mapped onto the columns within reach
        self.poles = list(poles)
        self.pole_map = np.full(model.nx * model.nz, -1, np.int32)
        for k, p in enumerate(self.poles):
            for c in self._disc(p['x'], p['z'], self.PREACH + 0.05):
                self.pole_map[c] = k
        # rails: segments (a, b) per rail, mapped onto columns within reach
        self.rails = list(rails)
        segs = []
        for k, r in enumerate(self.rails):
            pts = r['points']
            s = 0.0
            for a, b in zip(pts[:-1], pts[1:]):
                ln = math.dist(a, b)
                if ln > 1e-6:
                    segs.append((k, a, b, s, ln))
                s += ln
        self.segs = segs
        self.seg_a = np.array([s[1] for s in segs]).reshape(-1, 3)
        self.seg_b = np.array([s[2] for s in segs]).reshape(-1, 3)
        self.seg_rail = np.array([s[0] for s in segs], np.int64)
        self.seg_s0 = np.array([s[3] for s in segs])
        self.seg_len = np.array([s[4] for s in segs])
        self.rail_map = np.full((model.nx * model.nz, 2), -1, np.int32)
        for i, (k, a, b, s0, ln) in enumerate(segs):
            for c in self._corridor(a, b, self.RREACH + 0.2):
                slot = 0 if self.rail_map[c, 0] < 0 else 1
                self.rail_map[c, slot] = i
        # pickups: boxes |dx| < 0.8, |dz| < 0.8, |dy| < 1.2 from the body's middle
        self.pickups = list(pickups)
        self.pick_map = np.full((model.nx * model.nz, 3), -1, np.int32)
        for k, p in enumerate(self.pickups):
            for c in self._square(p['x'], p['z'], 0.8):
                row = self.pick_map[c]
                free = np.nonzero(row < 0)[0]
                if len(free):
                    self.pick_map[c, free[0]] = k
        self.pick_xyz = np.array([[p['x'], p['y'], p['z']] for p in self.pickups]).reshape(-1, 3)

    # ---- column helpers

    def _square(self, x, z, h):
        m = self.m
        g = m.grid
        xs = np.arange(math.ceil((x - h - m.ox) / g), math.floor((x + h - m.ox) / g) + 1)
        zs = np.arange(math.ceil((z - h - m.oz) / g), math.floor((z + h - m.oz) / g) + 1)
        xs = xs[(xs >= 0) & (xs < m.nx)]
        zs = zs[(zs >= 0) & (zs < m.nz)]
        return [int(j * m.nx + i) for j in zs for i in xs]

    def _disc(self, x, z, r):
        m = self.m
        out = []
        for c in self._square(x, z, r + m.grid):
            cx, cz = m.xz_of(c)
            if (cx - x) ** 2 + (cz - z) ** 2 <= (r + m.grid * 0.75) ** 2:
                out.append(c)
        return out

    def _corridor(self, a, b, r):
        m = self.m
        n = max(int(math.dist((a[0], a[2]), (b[0], b[2])) / (m.grid * 0.5)) + 1, 1)
        cells = set()
        for k in range(n + 1):
            t = k / n
            x = a[0] + (b[0] - a[0]) * t
            z = a[2] + (b[2] - a[2]) * t
            cells.update(self._square(x, z, r))
        return cells

    # ---- flying

    def fly(self, b, trace=False, record_events=True, release_every=30):
        m = self.m
        n = len(b)
        F = m.floors
        Cl = m.ceilings
        W = m.walls
        fy, fny = F.y, F.extra['ny']
        cy = Cl.y if len(Cl) else np.zeros(1)
        whx, whz, wny = W.extra.get('hx'), W.extra.get('hz'), W.extra.get('ny')
        x, y, z = b.x.astype(float).copy(), b.y.astype(float).copy(), b.z.astype(float).copy()
        yaw, vy, fwd = b.yaw.astype(float).copy(), b.vy.astype(float).copy(), b.fwd.astype(float).copy()
        ctrl, cap, stick = b.ctrl.astype(float), b.cap.astype(float).copy(), b.stick.astype(float).copy()
        st = b.st.astype(np.int8)
        armed = b.glide.astype(bool).copy()
        dive_at = b.dive.astype(bool).copy()
        state = b.filled('state').astype(np.int8).copy()
        skip_pole = b.filled('skip_pole').astype(np.int64)
        skip_rail = b.filled('skip_rail').astype(np.int64)
        glided = np.zeros(n, bool)
        slid = np.zeros(n, bool)            # sliding down a wall: no more horizontal motion
        outcome = np.zeros(n, np.int8)
        ex, ey, ez = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        etick = np.zeros(n, np.int32)
        efloor = np.full(n, -1, np.int64)
        es = np.full(n, np.nan)
        ev = np.full(n, np.nan)
        maxy = y.copy()
        hole_x, hole_z = np.full(n, np.nan), np.full(n, np.nan)
        out_x, out_z, out_y = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        kicks = {k: [] for k in ('i', 'tick', 'x', 'y', 'z', 'yaw_in', 'speed', 'nx', 'nz')}
        rel = {k: [] for k in ('i', 'tick', 'gtime', 'x', 'y', 'z', 'yaw', 'fwd', 'vy')}
        picks = {k: [] for k in ('i', 'entity', 'tick', 'state')}
        traces = [[] for _ in range(n)] if trace else None
        x0, z0, x1, z1 = m.frame
        act = np.arange(n)
        gtime = np.zeros(n, np.int32)
        for tick in range(1, b.max_ticks + 1):
            if len(act) == 0:
                break
            a = act
            # the glider at the apex of the double or third jump (A held since take-off)
            dep = (state[a] == AIR) & armed[a] & ~glided[a] & (vy[a] <= 0) & ((st[a] == ST_DOUBLE) | (st[a] == ST_THIRD))
            if dep.any():
                i = a[dep]
                state[i] = GLIDE
                glided[i] = True
            dv = (state[a] == AIR) & dive_at[a] & (vy[a] <= 0)
            if dv.any():
                i = a[dv]
                fwd[i] = np.minimum(np.maximum(fwd[i], 0) + self.DIVEB, self.DIVEMAX)
                vy[i] = np.maximum(vy[i], self.DIVEVY)
                state[i] = DIVE
                dive_at[i] = False
            s = state[a]
            air = s == AIR
            gl = s == GLIDE
            dvs = s == DIVE
            # speeds
            if air.any():
                i = a[air]
                before = fwd[i]
                f = before + self.AIRACC * ctrl[i] * stick[i]
                c = cap[i]
                f = np.where(f > c, np.maximum(np.minimum(f, before) - self.AIRDRAG, c), f)
                fwd[i] = np.maximum(f, -self.AIRMAX / 2)
                vy[i] = np.maximum(vy[i] - self.G, -self.FALL)
            if gl.any():
                i = a[gl]
                fwd[i] += (self.GS - fwd[i]) * self.GE
                vy[i] += (-self.SINK - vy[i]) * self.GE
                gtime[i] += 1
                if record_events:
                    r = i[gtime[i] % release_every == 0]
                    if len(r):
                        for k, v in (('i', r), ('tick', np.full(len(r), tick)), ('gtime', gtime[r].copy()), ('x', x[r]),
                                     ('y', y[r]), ('z', z[r]), ('yaw', yaw[r]), ('fwd', fwd[r]), ('vy', vy[r])):
                            rel[k].append(v)
            if dvs.any():
                i = a[dvs]
                vy[i] = np.maximum(vy[i] - self.G, -self.FALL)
            sl = slid[a]
            f = np.where(sl, 0.0, fwd[a])
            dx = np.sin(yaw[a]) * f
            dz = np.cos(yaw[a]) * f
            nxp = x[a] + dx
            nzp = z[a] + dz
            col = m.col_of(nxp, nzp)
            w = m.wall_at(col, y[a])
            hit = w >= 0
            # into a wall: the part of the move along it, if that is free
            wall_n = np.zeros((len(a), 2))
            if hit.any() and len(W):
                hi = np.nonzero(hit)[0]
                wi = w[hi]
                hxv, hzv = whx[wi], whz[wi]
                # the face met is the one turned toward the body (a wall pushes only out of its
                # front): a column may keep the back face's normal of a thin wall
                back = dx[hi] * hxv + dz[hi] * hzv > 0
                hxv = np.where(back, -hxv, hxv)
                hzv = np.where(back, -hzv, hzv)
                wall_n[hi, 0], wall_n[hi, 1] = hxv, hzv
                d = dx[hi] * hxv + dz[hi] * hzv
                tx = dx[hi] - d * hxv
                tz = dz[hi] - d * hzv
                c2 = m.col_of(x[a][hi] + tx, z[a][hi] + tz)
                free = m.wall_at(c2, y[a][hi]) < 0
                nxp[hi] = np.where(free, x[a][hi] + tx, x[a][hi])
                nzp[hi] = np.where(free, z[a][hi] + tz, z[a][hi])
                col[hi] = np.where(free, c2, m.col_of(x[a][hi], z[a][hi]))
            oldy = y[a].copy()
            x[a], z[a] = nxp, nzp
            # air_wall(): a ledge in reach, or a wall to slide down and kick off
            done_mask = np.zeros(len(a), bool)
            if hit.any():
                hi = np.nonzero(hit & (s != DIVE))[0]
                if len(hi):
                    ai = a[hi]
                    hxv, hzv = wall_n[hi, 0], wall_n[hi, 1]
                    vx = np.sin(yaw[ai]) * fwd[ai]
                    vz = np.cos(yaw[ai]) * fwd[ai]
                    approach = -(vx * hxv + vz * hzv)
                    go = approach > 0
                    # the floor beyond the wall within reach
                    fxp = x[ai] - hxv * (self.R + 0.15)
                    fzp = z[ai] - hzv * (self.R + 0.15)
                    fc = m.col_of(fxp, fzp)
                    fl = m.floor_below(fc, oldy[hi] + self.LHIGH)
                    ly = np.where(fl >= 0, fy[np.maximum(fl, 0)], -1e9)
                    ok = go & (fl >= 0) & (ly >= oldy[hi] + self.LLOW) & (fny[np.maximum(fl, 0)] >= 0.8)
                    if ok.any():
                        ce = m.ceiling_above(fc, ly + 0.05)
                        room = (ce < 0) | (cy[np.maximum(ce, 0)] >= ly + self.H)
                        ok &= room
                    rising = (vy[ai] > 0) & (oldy[hi] + vy[ai] * vy[ai] / (self.G * 2) >= ly + 0.12)
                    grab = ok & ~rising
                    if grab.any():
                        gi = ai[grab]
                        outcome[gi] = LEDGE
                        ex[gi], ey[gi], ez[gi] = fxp[grab], ly[grab], fzp[grab]
                        efloor[gi] = fl[grab]
                        etick[gi] = tick
                        done_mask[hi[grab]] = True
                    # a wall slide: upright enough, met fast enough (not while rising past a ledge)
                    upright = np.abs(wny[w[hi]]) <= self.KTILT if len(W) else np.zeros(len(hi), bool)
                    ks = go & ~ok & upright & (approach >= self.KMIN) & ~slid[ai]
                    if ks.any():
                        ki = ai[ks]
                        if record_events:
                            for k, v in (('i', ki), ('tick', np.full(len(ki), tick)), ('x', x[ki]), ('y', oldy[hi][ks]),
                                         ('z', z[ki]), ('yaw_in', yaw[ki]), ('speed', np.abs(fwd[ki])),
                                         ('nx', hxv[ks]), ('nz', hzv[ks])):
                                kicks[k].append(v)
                        slid[ki] = True
                        fwd[ki] = 0.0
                        state[ki] = AIR           # a glide ends in the wall slide
                        stick[ki] = 0.0
                        vy[ki] = np.minimum(vy[ki], 0.0)
                hd = np.nonzero(hit & (s == DIVE))[0]
                if len(hd):
                    di = a[hd]
                    fwd[di] = 0.0
                    state[di] = AIR
            # vertical
            ny_ = oldy + vy[a]
            y[a] = ny_
            # move_h() pushes the body out of every wall it is in, moving or not: a body that came
            # down into a sloped wall (a face steeper than a floor) is pushed off it along its
            # normal, so it slides down the face rather than through it
            if len(W):
                wi = m.wall_at(col, ny_)
                inw = (wi >= 0) & ~done_mask
                if inw.any():
                    ii = np.nonzero(inw)[0]
                    hxv, hzv = whx[wi[ii]], whz[wi[ii]]
                    moved = np.zeros(len(ii), bool)
                    for dist in (0.12, 0.25, 0.4, 0.6):
                        left = ~moved
                        if not left.any():
                            break
                        jj = ii[left]
                        px = x[a[jj]] + hxv[left] * dist
                        pz = z[a[jj]] + hzv[left] * dist
                        c3 = m.col_of(px, pz)
                        ok3 = m.wall_at(c3, ny_[jj]) < 0
                        if ok3.any():
                            kk = jj[ok3]
                            x[a[kk]], z[a[kk]] = px[ok3], pz[ok3]
                            col[kk] = c3[ok3]
                            sel = np.nonzero(left)[0][ok3]
                            moved[sel] = True
            up = vy[a] > 0
            if up.any() and len(Cl):
                ui = np.nonzero(up)[0]
                head = ny_[ui] + self.H
                ce = m.ceiling_above(col[ui], head - vy[a][ui] - 0.02)
                bonk = (ce >= 0) & (cy[np.maximum(ce, 0)] < head)
                if bonk.any():
                    bi = ui[bonk]
                    y[a[bi]] = cy[ce[bonk]] - self.H - 0.01
                    vy[a[bi]] = 0.0
            top = np.maximum(oldy, y[a])
            fl = m.floor_below(col, top + self.STEP)
            fh = np.where(fl >= 0, fy[np.maximum(fl, 0)], -1e9)
            land = (fl >= 0) & (fh >= y[a]) & ~done_mask
            if land.any():
                li = a[land]
                outcome[li] = LAND
                y[li] = fh[land]
                ex[li], ey[li], ez[li] = x[li], y[li], z[li]
                efloor[li] = fl[land]
                etick[li] = tick
                done_mask |= land
            maxy[a] = np.maximum(maxy[a], y[a])
            inside = (x[a] >= x0) & (x[a] <= x1) & (z[a] >= z0) & (z[a] <= z1)
            # first flight over a column with nothing under the feet, inside the frame
            nofloor = (fl < 0) & inside & np.isnan(hole_x[a]) & ~done_mask
            if nofloor.any():
                ni = a[nofloor]
                hole_x[ni], hole_z[ni] = x[ni], z[ni]
            # pickups (the body's middle within the box)
            pc = self.pick_map[np.maximum(col, 0)]
            pc[col < 0] = -1
            for slot in range(pc.shape[1]):
                k = pc[:, slot]
                cand = k >= 0
                if not cand.any():
                    continue
                ci = np.nonzero(cand)[0]
                kk = k[ci]
                ai = a[ci]
                d = self.pick_xyz[kk] - np.stack([x[ai], y[ai] + self.H / 2, z[ai]], axis=1)
                got = (np.abs(d[:, 0]) < 0.8) & (np.abs(d[:, 1]) < 1.2) & (np.abs(d[:, 2]) < 0.8)
                if got.any():
                    picks['i'].append(ai[got])
                    picks['entity'].append(kk[got])
                    picks['tick'].append(np.full(int(got.sum()), tick))
                    picks['state'].append(state[ai[got]].astype(np.int8))
            # poles and rails: from the plain air states only (attach_air_grab from st_air)
            live = ~done_mask & (state[a] == AIR)
            if self.poles and live.any():
                pk = self.pole_map[np.maximum(col, 0)]
                cand = live & (pk >= 0) & (col >= 0) & (pk != skip_pole[a])
                if cand.any():
                    ci = np.nonzero(cand)[0]
                    for j in ci:
                        p = self.poles[pk[j]]
                        i = a[j]
                        ddx, ddz = x[i] - p['x'], z[i] - p['z']
                        if ddx * ddx + ddz * ddz > self.PREACH ** 2:
                            continue
                        if p['front'] and ddx * math.sin(p['ang']) + ddz * math.cos(p['ang']) < -0.05:
                            continue
                        if y[i] < p['y'] - 1.0 or y[i] > p['top'] - self.PTOP + 0.3:
                            continue
                        outcome[i] = POLE
                        efloor[i] = pk[j]
                        ex[i], ey[i], ez[i] = x[i], min(max(y[i], p['y']), p['top'] - self.PTOP), z[i]
                        es[i] = p['ang'] if p['front'] else math.atan2(ddx, ddz)
                        etick[i] = tick
                        done_mask[j] = True
            if self.segs and live.any():
                rc = self.rail_map[np.maximum(col, 0)]
                for slot in range(2):
                    sk = rc[:, slot]
                    cand = live & ~done_mask & (sk >= 0) & (col >= 0)
                    if not cand.any():
                        continue
                    ci = np.nonzero(cand)[0]
                    si = sk[ci]
                    ai = a[ci]
                    A = self.seg_a[si]
                    B = self.seg_b[si]
                    P = np.stack([x[ai], y[ai] + 0.9, z[ai]], axis=1)
                    D = B - A
                    L2 = np.maximum((D * D).sum(1), 1e-9)
                    t = np.clip(((P - A) * D).sum(1) / L2, 0, 1)
                    N = A + D * t[:, None]
                    e3 = P - N
                    inbox = (np.abs(e3) < 1.2).all(1)
                    hdx, hdz = x[ai] - N[:, 0], z[ai] - N[:, 2]
                    near = inbox & (hdx * hdx + hdz * hdz <= self.RREACH ** 2) & (self.seg_rail[si] != skip_rail[ai])
                    upv = N[:, 1] - y[ai]
                    grind = near & (vy[ai] <= 0) & (upv >= -0.05) & (upv <= -vy[ai] + 0.05)
                    hang = near & ~grind & (upv >= 1.2) & (upv <= 1.9)
                    for mask, code in ((grind, RAIL), (hang, HANG)):
                        if not mask.any():
                            continue
                        gi = ai[mask]
                        outcome[gi] = code
                        efloor[gi] = self.seg_rail[si[mask]]
                        es[gi] = self.seg_s0[si[mask]] + t[mask] * self.seg_len[si[mask]]
                        dd = D[mask] / np.sqrt(L2[mask])[:, None]
                        along = np.sin(yaw[gi]) * fwd[gi] * dd[:, 0] + np.cos(yaw[gi]) * fwd[gi] * dd[:, 2]
                        sign = np.where(along < 0, -1.0, 1.0)
                        ev[gi] = np.where(code == RAIL, np.maximum(np.abs(along), self.tn.mps('GrindMin')) * sign,
                                          0.0)
                        if code == HANG:
                            ev[gi] = sign
                        ex[gi], ey[gi], ez[gi] = N[mask, 0], N[mask, 1] - (0 if code == RAIL else 1.75), N[mask, 2]
                        etick[gi] = tick
                        done_mask[ci[mask]] = True
            # out of the frame, or below everything
            out = ~done_mask & ~inside
            if out.any():
                oi = a[out]
                outcome[oi] = OUT
                out_x[oi], out_z[oi], out_y[oi] = x[oi], z[oi], y[oi]
                ex[oi], ey[oi], ez[oi] = x[oi], y[oi], z[oi]
                etick[oi] = tick
                done_mask |= out
            fell = ~done_mask & (y[a] < self.ymin)
            if fell.any():
                fi = a[fell]
                outcome[fi] = FELL
                ex[fi], ey[fi], ez[fi] = x[fi], y[fi], z[fi]
                etick[fi] = tick
                done_mask |= fell
            if trace:
                for j, i in enumerate(a):
                    traces[i].append((float(x[i]), float(y[i]), float(z[i]), int(state[i])))
            act = a[~done_mask]
        if len(act):
            outcome[act] = TIMEOUT
            ex[act], ey[act], ez[act] = x[act], y[act], z[act]
            etick[act] = b.max_ticks

        def cat(d, types):
            return {k: (np.concatenate(v) if v else np.zeros(0, types.get(k, float))) for k, v in d.items()}
        return Result(outcome, ex, ey, ez, etick, efloor, es, ev, maxy, hole_x, hole_z, out_x, out_z, out_y, glided,
                      kicks=cat(kicks, {'i': np.int64, 'tick': np.int64}),
                      releases=cat(rel, {'i': np.int64, 'tick': np.int64, 'gtime': np.int64}),
                      pickups=cat(picks, {'i': np.int64, 'entity': np.int64, 'tick': np.int64, 'state': np.int8}),
                      trace=traces)
