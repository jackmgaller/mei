"""The robot's moves: one model shared by the reach map (sim.py flies them over the column
world) and the headless confirmer (confirm.py drives the real cart with the same inputs).

Each move is a take-off from a floor: the state player.akr's jump() (or the attachment's) puts
the body in, the stick held while it flies, and the pad script that makes the real controller do
it. Numbers come from the cart's tuning (tuning.py); nothing is restated here.

Air states (sim.py): AIR (st_air: jumps, flips, falls, kicks), GLIDE (st_glide), DIVE (st_dive).
"""
from dataclasses import dataclass
import math

AIR, GLIDE, DIVE = 0, 1, 2

# the controller's St names the confirmer's driver uses (player.akr's enum St)
ST_JUMP, ST_DOUBLE, ST_THIRD, ST_LONG, ST_BACKFLIP, ST_SIDEFLIP, ST_FALL, ST_KICK = range(8)


@dataclass(frozen=True)
class Move:
    name: str
    what: str
    st: int                 # ST_*: which jump (decides the glider and the air control)
    run: bool               # taken from a run (fwd = run speed) or standing
    vy: str                 # how the take-off's vertical speed is made (see launch_state)
    fwd: str
    stick: int              # in the air: 1 toward the heading, 0 neutral, -1 back
    glide: bool = False     # hold A through the apex: the glider
    dive_at_apex: bool = False
    backwards: bool = False  # travels against the facing (the backflip)
    script: int = 0         # the confirmer driver's mode (confirm.py)


# The take-offs from a floor. `script` numbers are the explore harness's modes.
MOVES = [
    Move('walk_off', 'run off the edge', ST_FALL, True, 'zero', 'run', 1, script=1),
    Move('hop', 'a standing jump, the stick held', ST_JUMP, False, 'jump', 'zero', 1, script=2),
    Move('jump', 'a running jump', ST_JUMP, True, 'jump', 'run', 1, script=3),
    Move('double', 'a running double jump', ST_DOUBLE, True, 'double', 'run', 1, script=4),
    Move('double_stand', 'a double jump from a hop on the spot', ST_DOUBLE, False, 'double', 'zero', 1, script=5),
    Move('third', 'a running triple jump', ST_THIRD, True, 'third', 'run', 1, script=6),
    Move('double_glide', 'a running double jump, held: the glider', ST_DOUBLE, True, 'double', 'run', 1,
         glide=True, script=7),
    Move('third_glide', 'a running triple jump, held: the glider', ST_THIRD, True, 'third', 'run', 1,
         glide=True, script=8),
    Move('long', 'a long jump (crouch slide, jump)', ST_LONG, True, 'long', 'long', 1, script=9),
    Move('backflip', 'a backflip (crouch, jump)', ST_BACKFLIP, False, 'flip', 'back', 0, backwards=True, script=10),
    Move('side_flip', 'a side flip (run, turn back, jump)', ST_SIDEFLIP, True, 'flip', 'side', 1, script=11),
    Move('jump_dive', 'a running jump, dive at the apex', ST_JUMP, True, 'jump', 'run', 1, dive_at_apex=True,
         script=12),
    Move('double_dive', 'a running double jump, dive at the apex', ST_DOUBLE, True, 'double', 'run', 1,
         dive_at_apex=True, script=13),
]
BY_NAME = {m.name: m for m in MOVES}

# Moves made from an attachment or a wall (sim.py's later passes): names for the report.
KICK = 'wall_kick'
RELEASE = 'glide_release'
POLE_JUMP = 'pole_jump'
POLE_DROP = 'pole_drop'
GRIND_END = 'grind_off_end'
GRIND_JUMP = 'grind_jump'
HANG_JUMP = 'hang_jump'
HANG_DROP = 'hang_drop'
LEDGE = 'ledge_grab'
WALK = 'walk'
SLIDE = 'slide'
POLE = 'pole'
GRIND = 'grind'
HANG = 'hang'


def launch_state(move, tn):
    """(vy, fwd, ctrl, cap, glide_armed) per tick for a take-off, as player.akr's jump() sets
    them (pl.vel.y, pl.fwd) from the tuning tn (tuning.Tuning)."""
    run = tn.mps('RunSpeed') if move.run else 0.0
    add = max(run, 0.0) * tn.t['JumpSpeedAdd']
    vy = {'zero': 0.0, 'jump': tn.mps('JumpVy') + add, 'double': tn.mps('DoubleVy') + add,
          'third': tn.mps('ThirdVy') + add, 'long': tn.mps('LongVy'), 'flip': tn.mps('FlipVy')}[move.vy]
    fwd = {'zero': 0.0, 'run': run, 'long': min(run * tn.t['LongMul'], tn.mps('LongMax')),
           'back': -tn.mps('FlipBack'), 'side': tn.mps('SideFlip')}[move.fwd]
    ctrl = 0.35 if move.st in (ST_LONG, ST_BACKFLIP, ST_SIDEFLIP) else 1.0
    cap = tn.mps('LongMax') if move.st == ST_LONG else tn.mps('AirMax')
    return vy, fwd, ctrl, cap, move.glide


def can_glide_from(move, tn):
    """The glider comes out of the double or the third jump, by T.GlideMode (tuning.akr)."""
    mode = int(tn.t['GlideMode'])
    if move.st == ST_DOUBLE:
        return mode != 0
    if move.st == ST_THIRD:
        return mode != 1
    return False


def headings(n):
    return [2 * math.pi * k / n for k in range(n)]
