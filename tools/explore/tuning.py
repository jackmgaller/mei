"""The robot's numbers, read from the cart: the tuning table's defaults (carts/garden/tuning.akr),
the controller's own constants (player.akr, attach.akr) and the game schema's probe (the body's
radius, height, step and crack bridge). Nothing here is a guess: a number the cart does not have
fails loudly.

Values are kept in the cart's units (m, m/s, m/s2, ticks); `per_tick` gives the per-tick forms
player.akr works in (mps(), mps2(), rps())."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import re

ROOT = Path(__file__).resolve().parents[2]
CART = ROOT / 'carts' / 'garden'


class TuningError(Exception):
    pass


def _strip_comments(text):
    return re.sub(r'//[^\n]*', '', text)


def read_tune_table(path):
    """{T name: default} from tuning.akr's `enum T` and `const TUNE` (same order)."""
    text = _strip_comments(Path(path).read_text())
    m = re.search(r'enum\s+T\s*\{(.*?)\}', text, re.S)
    if not m:
        raise TuningError(f'{path}: no enum T')
    names = [n.strip() for n in m.group(1).replace('\n', ' ').split(',') if n.strip()]
    m = re.search(r'const\s+TUNE\s*:[^=]*=\s*\[(.*)\]', text, re.S)
    if not m:
        raise TuningError(f'{path}: no const TUNE')
    defs = re.findall(r'TuneDef\s*\{[^}]*?def:\s*(-?[0-9.]+)', m.group(1))
    if len(defs) != len(names):
        raise TuningError(f'{path}: {len(names)} T entries but {len(defs)} TuneDef rows')
    return {n: float(v) for n, v in zip(names, defs)}


def read_consts(path, names):
    """{name: value} of `const NAME: fixed = V` (or `const NAME = V`) lines in an Akari file."""
    text = _strip_comments(Path(path).read_text())
    out = {}
    for n in names:
        m = re.search(rf'const\s+{n}\s*(?::\s*\w+)?\s*=\s*(-?[0-9.]+)', text)
        if not m:
            raise TuningError(f'{path}: no const {n}')
        out[n] = float(m.group(1))
    return out


def read_push_heights(path):
    text = _strip_comments(Path(path).read_text())
    m = re.search(r'const\s+PUSH_H\s*:[^=]*=\s*\[([^\]]*)\]', text)
    if not m:
        raise TuningError(f'{path}: no const PUSH_H')
    return [float(v) for v in m.group(1).split(',')]


def read_probe(path):
    """The game schema's probe block (Mochi): radius, height, step, floor_max_degrees, bridge."""
    text = Path(path).read_text()
    m = re.search(r'probe\s*\{(.*?)\}', _strip_comments(text), re.S)
    if not m:
        raise TuningError(f'{path}: no probe block')
    out = {}
    for k, v in re.findall(r'(\w+)\s*=\s*(-?[0-9.]+)', m.group(1)):
        out[k] = float(v)
    for k in ('radius', 'height', 'step', 'floor_max_degrees', 'bridge'):
        if k not in out:
            raise TuningError(f'{path}: the probe has no {k}')
    return out


@dataclass
class Tuning:
    t: dict                     # T name -> default (cart units)
    player: dict                # player.akr constants
    attach: dict                # attach.akr constants
    push_h: list                # the heights above the feet at which walls push
    probe: dict                 # the game schema's probe
    surfaces: list              # the pack's surface bytes to the controller's (ground.akr's WORLD_SURFACES)
    sources: list = field(default_factory=list)

    # ---- per tick, as player.akr's mps(), mps2(), rps()
    def mps(self, k):
        return self.t[k] / 60.0

    def mps2(self, k):
        return self.t[k] / 3600.0

    def rps(self, k):
        return self.t[k] / 60.0

    @property
    def radius(self):
        return self.probe['radius']

    @property
    def height(self):
        return self.probe['height']

    @property
    def step(self):
        return self.probe['step']

    @property
    def slide_ny(self):
        """A floor whose normal's y is below this slides (T.SlideAngle)."""
        return math.cos(math.radians(self.t['SlideAngle']))

    def summary(self):
        """The reaches the numbers come to, for the report (metres): what a body standing on a
        floor can get its feet onto, straight up, with each move and with a ledge grab."""
        g = self.t['Gravity']
        run = self.t['RunSpeed'] / 60.0
        add = run * self.t['JumpSpeedAdd'] * 60.0          # m/s added to a running take-off

        def apex(vy):           # the discrete integration's apex (harness.akr's apex_ticks)
            return vy * vy / (2 * g) - vy / 120.0
        rows = {
            'jump': apex(self.t['JumpVy']),
            'jump_running': apex(self.t['JumpVy'] + add),
            'double': apex(self.t['DoubleVy']),
            'double_running': apex(self.t['DoubleVy'] + add),
            'third_running': apex(self.t['ThirdVy'] + add),
            'backflip': apex(self.t['FlipVy']),
            'side_flip': apex(self.t['FlipVy']),
            'wall_kick': apex(self.t['KickVyGood']),
            'pole_jump': apex(self.t['PoleJumpVy']),
        }
        out = {k: round(v, 3) for k, v in rows.items()}
        out['ledge_high'] = self.t['LedgeHigh']
        out['highest_with_grab'] = round(max(rows.values()) + self.t['LedgeHigh'], 3)
        out['glide_ratio'] = round(self.t['GlideSpeed'] / self.t['GlideSink'], 3)
        return out


def load(cart=CART, game_schema=None):
    cart = Path(cart)
    tune = cart / 'tuning.akr'
    player = cart / 'player.akr'
    attach = cart / 'attach.akr'
    schema = Path(game_schema) if game_schema else cart / 'world' / 'garden.game.mochi'
    t = read_tune_table(tune)
    pc = read_consts(player, ['LEDGE_HANG', 'LEDGE_GRAB_TICKS', 'DIVE_MIN', 'SKID_ANGLE',
                              'WADE_NO_JUMP'])
    ac = read_consts(attach, ['POLE_HOLD', 'HANG_BELOW'])
    ground = cart / 'ground' / 'ground.akr'
    m = re.search(r'const\s+WORLD_SURFACES\s*:[^=]*=\s*\[([^\]]*)\]', _strip_comments(ground.read_text()))
    if not m:
        raise TuningError(f'{ground}: no const WORLD_SURFACES')
    surfaces = [int(v) for v in m.group(1).split(',')]
    return Tuning(t=t, player=pc, attach=ac, push_h=read_push_heights(player), probe=read_probe(schema),
                  surfaces=surfaces, sources=[str(p.relative_to(ROOT)) for p in (tune, player, attach, schema, ground)])
