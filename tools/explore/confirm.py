"""The headless confirmer: each suspicious find of the reach map flown again by the real cart.

For a find, the explorer's probe stands the body where the flight took off, puts the controller
in the state the move starts from (moves.py: the run speed, the chain after a landing, a crouch
or a skid, a pole held) and presses the move's buttons; the stick follows the move's heading,
and the later presses the flight made (a wall kick on a wall slide, letting go of a glide, a
dive at the apex) come when the controller gets there. Every tick it watches whether the body
left the level's frame, flew over a column with no floor under it, sank below the floor at its
spot, entered a watched box, covered a watched pickup. One headless run (mei-headless, the
garden's scenario harness) flies all of a world's probes in turn.

A find is tried up to `tries` times: the first exactly as found, then jittered by a seeded random
generator (the take-off moved up to 0.25 m, the heading up to 5 degrees). The seed, the try and
the probe are the repro; for each confirmed find a scenario is written in the harness's style
(the take-off, the inputs, and the checks that fail while the bug is there).

The harness is not edited: carts/garden/tests/*.akr are copied into the build directory and the
copy of harness.akr gets four hook lines (an import, the world, the init and the per-frame hook).
"""
from dataclasses import dataclass, field, asdict
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'carts' / 'garden' / 'tests'
SCENARIO = 990

MODE_POLE_JUMP, MODE_POLE_DROP = 20, 21
MODE_DROP = 40
RAIL_MODES = {'hang_jump': 22, 'hang_drop': 23, 'grind_jump': 24, 'grind_off_end': 25}
WORLD_CONST = {'garden': 'GARDEN_WORLD_GARDEN', 'shrine': 'GARDEN_WORLD_SHRINE', 'shrinetown': 'GARDEN_WORLD_SHRINETOWN'}


@dataclass
class Probe:
    find: str               # the find's id in the report
    p: tuple                # take-off (x, y, z)
    yaw: float              # the body's facing at the take-off (radians)
    head: float             # the stick's heading in the air
    mode: int               # moves.Move.script, or MODE_POLE_*
    t: int = 600
    kick: int = 0           # wall kicks to make
    kick_head: int = 1      # after a kick: 1 stick along the new facing, 0 none
    release: int = 0        # ticks of gliding before letting go (0: never)
    rstick: int = 1         # after letting go: 1 stick on, 0 none
    box: tuple = (0.0, 0.0, 0.0)
    half: tuple = (0.0, 0.0, 0.0)
    pick: tuple = (0.0, -1000.0, 0.0)
    run: float = 0.0
    seed: int = 0
    attempt: int = 0

    def jittered(self, rng, attempt):
        if attempt == 0:
            return self
        d = rng.uniform(0, 0.25)
        a = rng.uniform(0, 2 * math.pi)
        h = math.radians(rng.uniform(-5, 5))
        return Probe(**{**asdict(self), 'p': (self.p[0] + d * math.sin(a), self.p[1], self.p[2] + d * math.cos(a)),
                        'yaw': self.yaw + h, 'head': self.head + h, 'attempt': attempt})


@dataclass
class Outcome:
    k: int
    out: bool
    out_p: tuple
    hole_t: int
    hole_p: tuple
    under: float
    inbox: int
    pick_st: int
    end: tuple
    st: str
    maxy: float
    miny: float
    land: tuple
    states: int
    through: int = -1
    through_p: tuple = (0.0, 0.0, 0.0)
    raw: str = ''


def _f(v):
    s = f'{float(v):.4f}'
    return s


def probes_akr(probes, frame, world, ymin=-1000.0, nodraw=True, checks=None):
    rows = []
    for q in probes:
        rows.append('    ExProbe { p: vec3(%s, %s, %s), yaw: %s, head: %s, mode: %d, t: %d, kick: %d, kick_head: %d, '
                    'release: %d, rstick: %d, box: vec3(%s, %s, %s), half: vec3(%s, %s, %s), pick: vec3(%s, %s, %s), run: %s },'
                    % (_f(q.p[0]), _f(q.p[1]), _f(q.p[2]), _f(wrap(q.yaw)), _f(wrap(q.head)), q.mode, q.t, q.kick,
                       q.kick_head, q.release, q.rstick, *(_f(v) for v in q.box), *(_f(v) for v in q.half),
                       *(_f(v) for v in q.pick), _f(q.run)))
    x0, z0, x1, z1 = frame
    return (DRIVER_HEAD.replace('@N@', str(len(probes))).replace('@ROWS@', '\n'.join(rows))
            .replace('@X0@', _f(x0)).replace('@Z0@', _f(z0)).replace('@X1@', _f(x1)).replace('@Z1@', _f(z1))
            .replace('@WORLD@', WORLD_CONST[world]).replace('@YMIN@', _f(ymin))
            .replace('@NODRAW@', 'true' if nodraw else 'false') + DRIVER + checks_akr(checks))


def checks_akr(checks):
    """ex_check(k): the expectations per probe (none: EX_CHECK false and an empty function)."""
    if not checks:
        return '\nconst EX_CHECK = false\nfn ex_check(k: s32) {}\n'
    rows = []
    for k, c in enumerate(checks):
        if c:
            rows.append(f'        {k} => {{ {c} }}')
    return ('\nconst EX_CHECK = true\n\n// What each probe must show when it ends (each fails while its bug is there).\n'
            'fn ex_check(k: s32) {\n    match k {\n' + '\n'.join(rows) + '\n        else => {}\n    }\n}\n')


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


DRIVER_HEAD = '''// Generated by tools/explore/confirm.py - the explorer's probes (a scratch scenario, 990).
struct ExProbe {
    p: vec3            // the take-off: x, the height to look down for the floor from, z
    yaw: fixed         // the body's facing
    head: fixed        // the stick's heading in the air (world yaw)
    mode: s32          // the move (tools/explore/moves.py script numbers; 20, 21: off a pole)
    t: s32             // ticks to watch
    kick: s32          // wall kicks to make (A at each wall slide)
    kick_head: s32     // after a kick: 1 the stick along the new facing
    release: s32       // ticks of gliding before letting go (0: never)
    rstick: s32        // after letting go: 1 the stick on
    box: vec3          // a box to watch: its centre ...
    half: vec3         // ... and half size (0: none)
    pick: vec3         // a pickup to watch (y below -999: none)
    run: fixed         // a glide case (mode 30): metres run before the jump
}

const EX_WORLD = @WORLD@
const EX_X0: fixed = @X0@
const EX_Z0: fixed = @Z0@
const EX_X1: fixed = @X1@
const EX_Z1: fixed = @Z1@
const EX_YMIN: fixed = @YMIN@        // below every floor of the world
const EX_NODRAW = @NODRAW@
const EX_PROBES: [@N@]ExProbe = [
@ROWS@
]
'''

DRIVER = '''
var ex_k: s32 = -1
var ex_f0: s32
var ex_ph: s32
var ex_kicks: s32
var ex_kick_yaw: fixed
var ex_glide_t: s32
var ex_released: bool
var ex_dived: bool
var ex_lasta: bool
var ex_out: bool
var ex_out_p: vec3
var ex_hole_t: s32
var ex_hole_p: vec3
var ex_under: fixed
var ex_inbox: s32
var ex_pick_st: s32
var ex_maxy: fixed
var ex_miny: fixed
var ex_land: vec3
var ex_landed: bool
var ex_states: u32
var ex_up: bool
var ex_through: s32
var ex_stop: s32
var ex_through_p: vec3

fn ex_case_init() -> bool {
    if SCENARIO != 990 { return false }
    name = "explorer probes"
    cam.lock = false
    return true
}

fn ex_floor(x: fixed, z: fixed, from: fixed) -> fixed {
    if wp_floor(vec3(x, from, z), 0.0) { return wp_hit.y }
    return -1000.0
}

fn ex_place(q: ExProbe) {
    let y = ex_floor(q.p.x, q.p.z, q.p.y + 0.5)
    place(vec3(q.p.x, y, q.p.z), q.yaw)
    pl.spawn = vec3(q.p.x, -1000.0, q.p.z)     // no respawn while it falls
}

fn ex_begin(f: s32) {
    let q = EX_PROBES[ex_k]
    ex_place(q)
    ex_f0 = f
    ex_ph = 0
    ex_kicks = 0
    ex_glide_t = 0
    ex_released = false
    ex_dived = false
    ex_out = false
    ex_hole_t = -1
    ex_under = -1000.0
    ex_inbox = -1
    ex_pick_st = -1
    ex_maxy = pl.pos.y
    ex_miny = pl.pos.y
    ex_landed = false
    ex_states = 0
    ex_up = false
    ex_kick_yaw = 0.0
    ex_through = -1
    ex_stop = 1000000
}

fn ex_pf(v: vec3) {
    print_fixed(v.x)
    print_char(' ')
    print_fixed(v.y)
    print_char(' ')
    print_fixed(v.z)
}

fn ex_end() {
    if EX_CHECK { ex_check(ex_k) }
    print("EXP ")
    print_int(ex_k)
    print(" out ")
    if ex_out { print("1 ") } else { print("0 ") }
    ex_pf(ex_out_p)
    print(" hole ")
    print_int(ex_hole_t)
    print_char(' ')
    ex_pf(ex_hole_p)
    print(" under ")
    print_fixed(ex_under)
    print(" inbox ")
    print_int(ex_inbox)
    print(" pick ")
    print_int(ex_pick_st)
    print(" end ")
    ex_pf(pl.pos)
    print(" st ")
    print_int(pl.st as s32)
    print(" maxy ")
    print_fixed(ex_maxy)
    print(" miny ")
    print_fixed(ex_miny)
    print(" land ")
    ex_pf(ex_land)
    print(" states ")
    print_int(ex_states as s32)
    print(" through ")
    print_int(ex_through)
    print_char(' ')
    ex_pf(ex_through_p)
    println("")
}

// The take-off state the move starts from (moves.py), set on the probe's second frame.
fn ex_takeoff(q: ExProbe) {
    ex_place(q)
    let m = q.mode
    if m == 1 || m == 3 || m == 4 || m == 6 || m == 7 || m == 8 || m == 12 || m == 13 { pl.fwd = mps(T.RunSpeed) }
    if m == 4 || m == 5 || m == 7 || m == 13 { pl.chain_from = St.Jump; pl.land_t = 0 }
    if m == 6 || m == 8 { pl.chain_from = St.DoubleJump; pl.land_t = 0 }
    if m == 9 { enter(St.CrouchSlide); pl.fwd = mps(T.RunSpeed) }
    if m == 10 { enter(St.Crouch); pl.fwd = 0.0 }
    if m == 11 { enter(St.Skid); pl.fwd = mps(T.SkidSpeed) }
    if m == 40 {                               // a drop: from the point, falling
        pl.pos = q.p
        pl.vel = vec3(0.0, 0.0, 0.0)
        pl.fwd = 0.0
        enter(St.Fall)
    }
    if m >= 22 && m <= 25 {                    // on a rail: hanging (22, 23) or grinding (24, 25)
        var hp = q.p
        if m <= 23 { hp = vec3(q.p.x, q.p.y + HANG_BELOW, q.p.z) }
        var held = false
        for k in 0..rail_n {
            if !held && wp_path_nearest(rails[k], hp, 1.2) {
                pl.yaw = q.head
                pl.fwd = mps(T.GrindMin)
                set_hvel()
                if m <= 23 { grab_rail(k, St.Hang) } else { grab_rail(k, St.Rail) }
                held = true
            }
        }
    }
    if m == 20 || m == 21 {
        var best = -1
        var bd = 1000.0
        for k in 0..pole_n {
            let d = abs(poles[k].base.x - q.p.x) + abs(poles[k].base.z - q.p.z)
            if d < bd { bd = d; best = k }
        }
        if best >= 0 {
            let b = poles[best].base
            pl.pos = vec3(b.x + sin(q.yaw) * 0.5, q.p.y, b.z + cos(q.yaw) * 0.5)
            grab_pole(best)
        }
    }
}

// A glide case (shrinetown_cases.akr's tw_glide, the same inputs): from q.p run q.run metres at
// the target q.box (its y: the lowest the feet may land), jump, hold to the apex, the chained
// double jump at the landing held through its apex (the glider), steering at the target; q.head
// is an aim error added to the steering until the second take-off.
fn ex_glide(q: ExProbe, g: s32) {
    let to = vec3(q.box.x, 0.0, q.box.z)
    var aim = atan2(to.x - pl.pos.x, to.z - pl.pos.z)
    if ex_ph < 3 { aim = aim + q.head }
    let steer = cc_stick(aim, 1.0)
    if g == 1 {
        let y = ex_floor(q.p.x, q.p.z, 90.0)
        place(vec3(q.p.x, y, q.p.z), aim)
        pl.spawn = vec3(q.p.x, -1000.0, q.p.z)
        ex_land = pl.pos
        ex_maxy = pl.pos.y
        ex_miny = pl.pos.y
        return
    }
    ex_states |= (1 << (pl.st as s32)) as u32
    ex_maxy = max(ex_maxy, pl.pos.y)
    ex_miny = min(ex_miny, pl.pos.y)
    let inside = pl.pos.x >= EX_X0 && pl.pos.x <= EX_X1 && pl.pos.z >= EX_Z0 && pl.pos.z <= EX_Z1
    if !inside && !ex_out { ex_out = true; ex_out_p = pl.pos }
    if q.pick.y > -999.0 && ex_pick_st < 0 {
        let d = q.pick - (pl.pos + vec3(0.0, BODY_HEIGHT / 2, 0.0))
        if abs(d.x) < 0.8 && abs(d.y) < 1.2 && abs(d.z) < 0.8 { ex_pick_st = pl.st as s32 }
    }
    let air = is_air(pl.st) || pl.st == St.Glide
    let ran = length(vec3(pl.pos.x - q.p.x, 0.0, pl.pos.z - q.p.z))
    if ex_ph == 0 {
        if q.run > 0.0 { stick_v = steer }
        if ran >= q.run && g > 3 { pad_v = A; ex_ph = 1 }
        return
    }
    if q.run > 0.0 { stick_v = steer }
    if ex_ph == 1 {
        pad_v = A
        if air && pl.vel.y <= 0.0 { pad_v = 0; ex_ph = 2 }
        return
    }
    if ex_ph == 2 {
        if pl.st == St.Ground { pad_v = A; ex_ph = 3 }
        return
    }
    if pl.st == St.Glide || q.run > 0.0 { stick_v = steer }
    if pl.st == St.LedgeHang || pl.st == St.LedgeClimb { stick_v = cc_stick(pl.yaw, 1.0) }
    if ex_ph == 3 {
        pad_v = A
        if !air && pl.st != St.LedgeHang && pl.st != St.LedgeClimb && pl.st != St.WallSlide {
            ex_ph = 4
            ex_land = pl.pos
            ex_landed = true
            ex_stop = g + 20
        }
        return
    }
    stick_v = STILL
}

fn ex_case(f: s32) {
    if SCENARIO != 990 { return }
    if ex_k < 0 { ex_k = 0; ex_begin(f) }
    if ex_k >= len(EX_PROBES) as s32 { return }   // all flown
    let q = EX_PROBES[ex_k]
    let g = f - ex_f0
    if g >= q.t + 2 || g >= ex_stop {
        ex_end()
        ex_k += 1
        if ex_k >= len(EX_PROBES) as s32 {
            println("EXDONE")
            done()
            if !EX_CHECK { assert(false) }   // the explorer's own runs stop here; a pasted case runs on
            return
        }
        ex_begin(f)
        return
    }
    if g == 0 { return }                       // standing still a frame: A released
    let m = q.mode
    if m == 30 { ex_glide(q, g); return }
    let steer = cc_stick(q.head, 1.0)
    if g == 1 {
        ex_takeoff(q)
        if m != 1 && m != 21 && m != 40 && m < 22 { pad_v = A }
        if m == 21 { pad_v = R }
        if m != 10 && m != 40 { stick_v = steer }
        ex_lasta = pad_v == A
        return
    }
    if g == 2 { ex_maxy = pl.pos.y; ex_miny = pl.pos.y }
    // watching
    ex_states |= (1 << (pl.st as s32)) as u32
    ex_maxy = max(ex_maxy, pl.pos.y)
    ex_miny = min(ex_miny, pl.pos.y)
    let inside = pl.pos.x >= EX_X0 && pl.pos.x <= EX_X1 && pl.pos.z >= EX_Z0 && pl.pos.z <= EX_Z1
    if !inside && !ex_out { ex_out = true; ex_out_p = pl.pos }
    if inside {
        if ex_hole_t < 0 && !wp_floor(vec3(pl.pos.x, pl.pos.y + 0.3, pl.pos.z), 0.0) { ex_hole_t = g; ex_hole_p = pl.pos }
        if ex_through < 0 && pl.pos.y < EX_YMIN { ex_through = g; ex_through_p = pl.pos }
        let top = ex_floor(pl.pos.x, pl.pos.z, 2000.0)
        if top > -999.0 { ex_under = max(ex_under, top - pl.pos.y) }
    }
    if q.half.x > 0.0 && ex_inbox < 0 {
        let d = pl.pos - q.box
        if abs(d.x) <= q.half.x && abs(d.y) <= q.half.y && abs(d.z) <= q.half.z { ex_inbox = g }
    }
    if q.pick.y > -999.0 && ex_pick_st < 0 {
        let d = q.pick - (pl.pos + vec3(0.0, BODY_HEIGHT / 2, 0.0))
        if abs(d.x) < 0.8 && abs(d.y) < 1.2 && abs(d.z) < 0.8 { ex_pick_st = pl.st as s32 }
    }
    let air = is_air(pl.st) || pl.st == St.Glide
    if air { ex_up = true }
    if ex_up && !ex_landed && pl.st == St.Ground { ex_landed = true; ex_land = pl.pos }
    // the stick
    var st = steer
    if m == 10 || m == 40 { st = STILL }
    if ex_kicks > 0 { if q.kick_head == 1 { st = cc_stick(ex_kick_yaw, 1.0) } else { st = STILL } }
    if ex_released { if q.rstick == 1 { st = cc_stick(pl.yaw, 1.0) } else { st = STILL } }
    if pl.st == St.LedgeHang || pl.st == St.LedgeClimb { st = cc_stick(pl.yaw, 1.0) }
    stick_v = st
    // the buttons
    var a = false
    let glide = m == 7 || m == 8
    if pl.st == St.Glide { ex_glide_t += 1 }
    if air || pl.st == St.WallSlide {
        a = ex_lasta
        if !glide && pl.vel.y <= 0.0 && (m == 4 || m == 5 || m == 6 || m == 13) { a = false }
        if glide && !ex_released { a = true }
        if q.release > 0 && ex_glide_t >= q.release { ex_released = true; a = false }
    }
    if (m == 12 || m == 13) && !ex_dived && is_air(pl.st) && pl.vel.y <= 0.0 { pad_v |= B; ex_dived = true }
    if pl.st == St.WallSlide && ex_kicks < q.kick {
        if ex_lasta { a = false } else { a = true; ex_kicks += 1 }
    }
    if pl.st == St.WallKick && ex_kicks > 0 && ex_kick_yaw == 0.0 { ex_kick_yaw = pl.yaw }
    if m == 20 && g < 4 { a = g == 2 }
    if (m == 22 || m == 24) && g == 3 { a = true }       // a hang jump or a grind jump, a tick after the grab
    if m == 23 && g == 3 { pad_v |= R }                   // off the hang: let go
    if a { pad_v |= A }
    ex_lasta = a
}
'''


def patch_harness(text):
    """The harness with the explorer's hooks: four lines, each checked."""
    subs = [
        ('import "goals_cases.akr"', 'import "goals_cases.akr"\nimport "explore_cases.akr"'),
        ('fn start_world() -> s32 {', 'fn start_world() -> s32 {\n    if SCENARIO == 990 { return EX_WORLD }'),
        ('!goals_case_init()', '!goals_case_init() && !ex_case_init()'),
        ('            goals_case(f)\n', '            goals_case(f)\n            ex_case(f)\n'),
    ]
    for a, b in subs:
        if text.count(a) != 1:
            raise RuntimeError(f'harness.akr has changed: cannot hook the explorer at {a!r}')
        text = text.replace(a, b)
    return text


LINE = re.compile(r'EXP (\d+) out (\d) (\S+) (\S+) (\S+) hole (-?\d+) (\S+) (\S+) (\S+) under (\S+) inbox (-?\d+) '
                  r'pick (-?\d+) end (\S+) (\S+) (\S+) st (\d+) maxy (\S+) miny (\S+) land (\S+) (\S+) (\S+) states (-?\d+) '
                  r'through (-?\d+) (\S+) (\S+) (\S+)')


def parse(out):
    res = []
    for line in out.splitlines():
        m = LINE.search(line)
        if not m:
            continue
        g = m.groups()
        v = [float(x) for x in g]
        res.append(Outcome(k=int(v[0]), out=bool(int(v[1])), out_p=tuple(v[2:5]), hole_t=int(v[5]), hole_p=tuple(v[6:9]),
                           under=v[9], inbox=int(v[10]), pick_st=int(v[11]), end=tuple(v[12:15]), st=ST_NAMES[int(v[15])]
                           if int(v[15]) < len(ST_NAMES) else str(int(v[15])), maxy=v[16], miny=v[17], land=tuple(v[18:21]),
                           states=int(v[21]) & 0xFFFFFFFF, through=int(v[22]), through_p=tuple(v[23:26]), raw=line))
    return res


ST_NAMES = ["ground", "skid", "crouch", "crouch slide", "slide", "jump", "double jump", "third jump", "long jump",
            "backflip", "side flip", "fall", "wall kick", "bounce", "rollout", "glide", "wall slide", "ledge hang",
            "ledge climb", "pound spin", "pound fall", "pound land", "dive", "belly slide", "pole", "rail", "hang"]


def read_st_names():
    """player.akr's state names, in order (checked against the copy above)."""
    text = (ROOT / 'carts' / 'garden' / 'player.akr').read_text()
    m = re.search(r'const ST_NAMES[^=]*=\s*\[(.*?)\]', text, re.S)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else ST_NAMES


class Runner:
    """Builds and runs the probe cart for one world. The cart is the garden's game with one change
    in a copy of game.akr: with EX_NODRAW, draw() clears the screen and returns, so a probe costs
    the controller's ticks, not the renderer's (the physics are untouched). The copy sits in the
    build directory; the cart's own files are found through meic -I."""

    def __init__(self, build_dir, world, frame, ymin=-1000.0, work=None, log=print, draw=False, processes=0):
        self.build = Path(build_dir).resolve()
        self.world = world
        self.frame = frame
        self.ymin = ymin
        self.work = Path(work or self.build / 'explore' / world)
        self.log = log
        self.draw = draw
        self.processes = processes or min(os.cpu_count() or 1, 8)
        names = read_st_names()
        ST_NAMES[:] = names
        self.meic = Path(os.environ.get('MEIC', self.build / 'meic'))
        self.run_ = Path(os.environ.get('RUN', self.build / 'mei-headless'))
        self.worlds = self.build / 'cart-worlds' / 'garden'
        for p in (self.meic, self.run_, self.worlds):
            if not p.exists():
                raise RuntimeError(f'{p} is not built: make B={self.build.name} first')
        self.ticks = 0
        self.seconds = 0.0

    def prepare(self, probes, d):
        d.mkdir(parents=True, exist_ok=True)
        for f in TESTS.glob('*.akr'):
            shutil.copy(f, d / f.name)
        (d / 'harness.akr').write_text(patch_harness((TESTS / 'harness.akr').read_text()))
        (d / 'explore_cases.akr').write_text(probes_akr(probes, self.frame, self.world, self.ymin, not self.draw))
        game = (ROOT / 'carts' / 'garden' / 'game.akr').read_text()
        hook = 'fn draw() {'
        if game.count(hook) != 1:
            raise RuntimeError('game.akr has changed: cannot find fn draw()')
        (d / 'explore_game.akr').write_text(game.replace(hook, hook + '\n    if EX_NODRAW { cls(rgb(0, 0, 0)); return }'))

    def _one(self, probes, name):
        d = self.work / name
        self.prepare(probes, d)
        frames = sum(q.t + 2 for q in probes) + 10
        scen = d / 'scenario.akr'
        scen.write_text(f'cart "Explorer"\nconst SCENARIO = {SCENARIO}\nconst SHOT = 1\nimport "harness.akr"\n'
                        f'import "explore_game.akr"\n')
        cart = d / 'probes.mei'
        pr = subprocess.run([str(self.meic), '-I', str(self.worlds), '-I', str(ROOT / 'carts' / 'garden'), str(scen), '-o',
                             str(cart)], capture_output=True, text=True)
        if pr.returncode != 0:
            raise RuntimeError('the probe cart did not compile:\n' + (pr.stdout + pr.stderr)[-3000:])
        return subprocess.Popen([str(self.run_), str(cart), '--frames', str(frames)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True), frames, d

    def run(self, probes, name='probes'):
        if not probes:
            return []
        t = time.perf_counter()
        n = len(probes)
        k = max(1, min(self.processes, (n + 7) // 8))
        parts = [list(range(i, n, k)) for i in range(k)]
        jobs = [self._one([probes[i] for i in part], f'{name}_{j}') for j, part in enumerate(parts)]
        got = []
        frames = 0
        for (proc, fr, d), part in zip(jobs, parts):
            out, _ = proc.communicate()
            (d / 'run.log').write_text(out)
            frames += fr
            for o in parse(out):
                o.k = part[o.k]
                got.append(o)
        dt = time.perf_counter() - t
        self.ticks += frames
        self.seconds += dt
        self.log(f'  headless: {n} probes, {frames:,} ticks in {dt:.1f} s over {k} runs'
                 + ('' if len(got) == n else f' ({len(got)} reported; see {self.work}/{name}_*/run.log)'))
        return sorted(got, key=lambda o: o.k)


# ---- turning finds into probes, and judging them

def probe_for_flight(fid, takeoff, extra=None):
    """A probe from a find's take-off (finds.describe_flight): the chain's first move from where
    it took off, then its wall kicks and its let-go of the glide."""
    from .moves import BY_NAME
    name = takeoff['move']
    head = math.radians(takeoff['heading_deg'])
    q = dict(find=fid, t=900)
    if name in BY_NAME:
        m = BY_NAME[name]
        q.update(p=tuple(takeoff['from']), yaw=head + (math.pi if m.backwards else 0.0), head=head, mode=m.script)
    elif name in ('pole_jump', 'pole_drop'):
        q.update(p=tuple(takeoff['from']), yaw=head, head=head,
                 mode=MODE_POLE_JUMP if name == 'pole_jump' else MODE_POLE_DROP)
    elif name in RAIL_MODES:
        q.update(p=tuple(takeoff['from']), yaw=head, head=head, mode=RAIL_MODES[name])
    else:
        return None
    q['kick'] = int(takeoff.get('kicks', 0))
    q['release'] = int(takeoff.get('release_ticks', 0))
    q['t'] = min(max(int(takeoff.get('seconds_before', 0) * 60) + int(takeoff.get('ticks', 600)) + 120, 240), 3000)
    q.update(extra or {})
    return Probe(**q)


def judge(kind, o, find):
    """Whether a probe's outcome shows the find."""
    if kind == 'escape':
        return o.out
    if kind in ('fall_through', 'drop'):
        return o.through >= 0
    if kind in ('sealed', 'leg'):
        return o.inbox >= 0
    if kind == 'glide_take':
        return o.pick_st == ST_NAMES.index('glide')
    if kind == 'take':
        return o.pick_st >= 0
    return False


def confirm(runner, items, tries=3, seed=1, judges=None):
    """items: [(kind, find dict, Probe)]. Flies every probe, then the jittered tries of those not
    yet shown, up to `tries` rounds. Returns per item: {'confirmed', 'attempt', 'seed', 'probe',
    'outcome'}."""
    rng = random.Random(seed)
    state = [{'confirmed': False, 'attempts': 0, 'seed': seed} for _ in items]
    for attempt in range(tries):
        todo = [k for k, s in enumerate(state) if not s['confirmed'] and items[k][2] is not None]
        if not todo:
            break
        probes = []
        for k in todo:
            q = items[k][2].jittered(rng, attempt)
            q.seed = seed
            probes.append(q)
        got = runner.run(probes, name=f'probes_{attempt}')
        by = {o.k: o for o in got}
        for j, k in enumerate(todo):
            o = by.get(j)
            s = state[k]
            s['attempts'] = attempt + 1
            if o is None:
                continue
            kind = items[k][0]
            ok = (judges[kind] if judges and kind in judges else judge)(kind, o, items[k][1])
            s['outcome'] = summary(o)
            s['probe'] = asdict(probes[j])
            if ok:
                s['confirmed'] = True
                s['attempt'] = attempt
    return state


def summary(o):
    return {'left_frame': o.out, 'left_at': [round(v, 2) for v in o.out_p] if o.out else None,
            'over_no_floor_tick': o.hole_t, 'over_no_floor_at': [round(v, 2) for v in o.hole_p] if o.hole_t >= 0 else None,
            'deepest_under_floor_m': round(o.under, 2), 'entered_box_tick': o.inbox,
            'pickup_state': ST_NAMES[o.pick_st] if 0 <= o.pick_st < len(ST_NAMES) else None,
            'end': [round(v, 2) for v in o.end], 'end_state': o.st, 'max_y': round(o.maxy, 2), 'min_y': round(o.miny, 2),
            'states_seen': [n for k, n in enumerate(ST_NAMES) if o.states >> k & 1],
            'fell_below_world_tick': o.through,
            'fell_below_world_at': [round(v, 2) for v in o.through_p] if o.through >= 0 else None}


# ---- a case to paste

CHECKS = {
    'escape': 'expect(!ex_out, "@ID@: stays in the level", ex_out_p.x)',
    'fall_through': 'expect(ex_through < 0, "@ID@: does not fall through the world", fixed(ex_through))',
    'drop': 'expect(ex_through < 0, "@ID@: does not fall through the world", fixed(ex_through))',
    'sealed': 'expect(ex_inbox < 0, "@ID@: does not get into the sealed place this way", fixed(ex_inbox))',
    'glide_take': 'expect(ex_pick_st != St.Glide as s32, "@ID@: the card is not taken gliding", fixed(ex_pick_st))',
}

CASE_HEAD = """// Generated by tools/explore/mei_explore.py - {title}
// The explorer found it in {world} (seed {seed}, try {attempt}); the case fails while the bug is
// there. Run it as it is: python3 tools/explore/mei_explore.py --run-case THIS_FILE --build-dir B
// (exit status 2 while it fails). Or paste it: as carts/garden/tests/explore_cases.akr, hooked in
// harness.akr as tools/explore/confirm.py patch_harness() hooks it (an import, the world for
// SCENARIO 990, ex_case_init() and ex_case(f)), then tests/run.sh 990 {frames} out
"""


def case_text(world, kind, find, st, frame=(0, 0, 320, 384), ymin=-1000.0):
    """A complete cases file for one find: the probe driver, the probe and its check."""
    q = Probe(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in st['probe'].items()})
    fid = find.get('id', kind)
    check = CHECKS.get(kind, '').replace('@ID@', fid)
    text = probes_akr([q], frame, world, ymin, nodraw=False, checks=[check])
    head = CASE_HEAD.format(title=find.get('title', kind), world=world, seed=st.get('seed', 0),
                            attempt=st.get('attempt', 0), frames=q.t + 12)
    return head + text.split('\n', 1)[1]


def run_case(build_dir, case, draw=True, log=print):
    """Runs a written case (cases/FIND.akr) in the real cart: the case as the harness's
    explore_cases.akr in a copy of the tests in the build directory, the game as it is (drawn,
    unless draw is false). Returns mei-headless's exit status (2: the check failed) and its output."""
    build = Path(build_dir).resolve()
    d = build / 'explore' / 'case'
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for f in TESTS.glob('*.akr'):
        shutil.copy(f, d / f.name)
    (d / 'harness.akr').write_text(patch_harness((TESTS / 'harness.akr').read_text()))
    text = Path(case).read_text()
    (d / 'explore_cases.akr').write_text(text)
    m = re.search(r'tests/run.sh 990 (\d+)', text)
    frames = int(m.group(1)) if m else 3000
    game = ROOT / 'carts' / 'garden' / 'game.akr'
    if not draw:
        src = game.read_text()
        (d / 'explore_game.akr').write_text(src.replace('fn draw() {', 'fn draw() {\n    if EX_NODRAW { cls(rgb(0, 0, 0)); return }'))
        text = text.replace('const EX_NODRAW = false', 'const EX_NODRAW = true')
        (d / 'explore_cases.akr').write_text(text)
        game = d / 'explore_game.akr'
    (d / 'scenario.akr').write_text(f'cart "Explorer case"\nconst SCENARIO = {SCENARIO}\nconst SHOT = 1\n'
                                     f'import "harness.akr"\nimport "{game}"\n')
    meic = Path(os.environ.get('MEIC', build / 'meic'))
    run = Path(os.environ.get('RUN', build / 'mei-headless'))
    worlds = build / 'cart-worlds' / 'garden'
    pr = subprocess.run([str(meic), '-I', str(worlds), '-I', str(ROOT / 'carts' / 'garden'), str(d / 'scenario.akr'), '-o',
                         str(d / 'case.mei')], capture_output=True, text=True)
    if pr.returncode != 0:
        return pr.returncode, pr.stdout + pr.stderr
    pr = subprocess.run([str(run), str(d / 'case.mei'), '--frames', str(frames)], capture_output=True, text=True)
    return pr.returncode, pr.stdout + pr.stderr


def glide_cases(path):
    """The glide constants of a cases file (const Gn: Glide = Glide { from, to, run, tol })."""
    text = Path(path).read_text()
    out = {}
    for m in re.finditer(r'const (G\d+): Glide = Glide \{ from: vec3\(([^)]*)\), to: vec3\(([^)]*)\), run: ([0-9.]+), '
                         r'tol: ([0-9.]+) \}', text):
        out[m.group(1)] = {'from': [float(v) for v in m.group(2).split(',')], 'to': [float(v) for v in m.group(3).split(',')],
                           'run': float(m.group(4)), 'tol': float(m.group(5))}
    return out
