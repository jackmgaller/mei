"""Plans for the thief, played on the rules' model (rules_model.py) into tapes; shared by the
rooms' and levels' solutions scripts.

A plan is a list of steps:
  ('go', x, z)         walk to the point (the stick, one direction while it still gets there)
  ('until', pred)      stand still until pred(sim) is true
  ('idle', n)          stand still n ticks
  ('press', 'A')       one tick holding A (or B, L)
"""
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules_model as S  # noqa: E402

NAMES = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'X', 'Y', 'L', 'R']


def guard(sim, gid):
    return sim.guards[[w['id'] for w in sim.watch].index(gid)]


def heading(sim, gid):
    return math.degrees(guard(sim, gid)['head']) % 360


def doors_open(sim, k):
    return sim.tstate[k]['open']


def tape_lines(const, inputs, comment):
    """A tape as Akari: the plan's inputs, then half a second walking on the same way (the cart's
    fixed point lands the thief a few centimetres from the model's position)."""
    last = next((i for i in reversed(inputs) if i[1] or i[2]), (0, 0, 0))
    sp = spans(inputs + [(0, last[1], last[2])] * 30)
    out = [f'// {comment}', f'const {const}: [{len(sp)}]Span = [']
    out += [f'    Span {{ n: {n}, pad: {pad_name(p)}, sx: {sx}, sy: {sy} }},' for n, p, sx, sy in sp]
    out.append(']\n')
    return out


def sheet(shots, path, cols=3):
    from PIL import Image
    if not shots:
        return
    w, h = shots[0].size
    rows = (len(shots) + cols - 1) // cols
    im = Image.new('RGB', (w * cols, h * rows))
    for i, s in enumerate(shots):
        im.paste(s, ((i % cols) * w, (i // cols) * h))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


# ---- playing a plan

def play(steps, sim, frames=(), limit=7200):
    """Plays a plan on a fresh room. Returns the result, the input of every tick, the nearest each
    watcher's fan came to the thief, and pictures at the given ticks."""
    inputs, path, shots, margins = [], [], [], {}
    result = None

    def emit(pad, sx=0, sy=0):
        nonlocal result
        if sim.clock in frames:
            shots.append(draw(sim, path))
        why, cleared = sim.tick(pad, sx, sy)
        inputs.append((pad, sx, sy))
        path.append((sim.th['x'], sim.th['z']))
        if not sim.th['hidden']:
            for g, w in zip(sim.guards, sim.watch):
                m = S.fan_dist(g['fan'], sim.th['x'], sim.th['z']) - (0.0 if S.RULES['centre'] else S.THIEF_R)
                if m < margins.get(w['id'], (99, 0))[0]:
                    margins[w['id']] = (round(m, 2), sim.clock - 1)
        if why:
            result = ('caught', why, sim.clock - 1)
        elif cleared:
            result = ('cleared', sim.clock - 1) if sim.left_by is None else ('cleared', sim.clock - 1, sim.left_by)
        return result

    for st in steps:
        op = st[0]
        if op == 'until':
            while not st[1](sim):
                if emit(0) or sim.clock > limit:
                    break
        elif op == 'press':
            emit({'A': S.A, 'B': S.B, 'L': S.L}[st[1]])
        elif op == 'idle':
            for _ in range(st[1]):
                if emit(0):
                    break
        elif op == 'go':
            tx, tz = st[1], st[2]
            aim, still = None, 0
            for _ in range(3000):
                dx, dz = tx - sim.th['x'], tz - sim.th['z']
                dd = math.hypot(dx, dz)
                if dd < 0.02:
                    break
                if dd < S.WALK:
                    sx, sy = round(127 * dx / S.WALK), round(127 * dz / S.WALK)
                    if abs(sx) < 27 and abs(sy) < 27:     # inside the stick's dead zone: there
                        break
                    aim = None
                else:
                    # one direction for as long as it passes within 2 cm of the point
                    if aim is not None:
                        n = math.hypot(*aim)
                        ux, uz = aim[0] / n, aim[1] / n
                        if abs(dx * uz - dz * ux) > 0.02 or dx * ux + dz * uz <= 0:
                            aim = None
                    if aim is None:
                        if abs(dx) < 1e-4 or abs(dz) < 1e-4:
                            aim = ((dx > 1e-4) * 127 - (dx < -1e-4) * 127, (dz > 1e-4) * 127 - (dz < -1e-4) * 127)
                        else:
                            aim = (round(127 * dx / dd), round(127 * dz / dd))
                    sx, sy = aim
                x0, z0 = sim.th['x'], sim.th['z']
                if emit(0, sx, sy):
                    break
                still = still + 1 if abs(sim.th['x'] - x0) < 1e-6 and abs(sim.th['z'] - z0) < 1e-6 else 0
                if still >= 3:
                    break     # against something
        if result:
            break
    return dict(result=result, inputs=inputs, margins=margins, shots=shots)


# ---- the tape

def spans(inputs):
    out = []
    for pad, sx, sy in inputs:
        if out and out[-1][1:] == [pad, sx, sy] and out[-1][0] < 65535:
            out[-1][0] += 1
        else:
            out.append([1, pad, sx, sy])
    return out


def pad_name(p):
    names = [NAMES[i] for i in range(10) if p >> i & 1]
    return ' | '.join(names) if names else '0'


# ---- pictures

def draw(sim, path):
    room = next(e for e in sim.ents.values() if e['type'] == 'room')
    cx, cz = room['position'][0], room['position'][2]
    sx, sz = room['params']['size'][0], room['params']['size'][2]
    ox, oz = cx - sx / 2 - 0.5, cz + sz / 2 + 0.5
    from PIL import Image, ImageDraw
    px = 28

    def at(x, z):
        return ((x - ox) * px, (oz - z) * px)
    im = Image.new('RGB', (int((sx + 1) * px), int((sz + 1) * px)), (20, 22, 28))
    d = ImageDraw.Draw(im, 'RGBA')
    d.rectangle([*at(cx - sx / 2, cz + sz / 2), *at(cx + sx / 2, cz - sz / 2)], fill=(110, 114, 122))
    for b in sim.walls:
        col = (40, 40, 44) if b.edge else (60, 66, 80) if b.blocks else (150, 120, 90)
        d.polygon([at(*p) for p in b.corners()], fill=col)
    for s in sim.spots:
        d.polygon([at(*p) for p in s.corners()], outline=(80, 120, 220))
    if sim.exit is not None:
        d.polygon([at(*p) for p in sim.exit.corners()], outline=(80, 220, 120))
    CARD = {'red': (230, 50, 50), 'blue': (60, 110, 255), 'green': (60, 200, 90), 'yellow': (240, 210, 40)}
    for dr in sim.doors:
        col = CARD.get(dr['card'], (80, 220, 120))
        if sim.door_shut(dr):
            d.polygon([at(*p) for p in dr['box'].corners()], fill=col)
        else:
            d.polygon([at(*p) for p in dr['box'].corners()], outline=col)
    for c in sim.cards_here:
        if c['id'] not in sim.taken:
            x, y = at(c['x'], c['z'])
            d.rectangle([x - 6, y - 4, x + 6, y + 4], fill=CARD[c['colour']])
    for tr, st in zip(sim.trains, sim.tstate):
        for c in st['cars']:
            b = tr.car_box(c, -c['len'] / 2, c['len'] / 2, -tr.width / 2, tr.width / 2)
            d.polygon([at(*p) for p in b.corners()], fill=(200, 190, 120, 120 if st['open'] else 200))
    for b in sim.dyn_boxes:
        d.polygon([at(*p) for p in b.corners()], fill=(240, 230, 150))
    for g, w in zip(sim.guards, sim.watch):
        ax, az, pts = g['fan']
        d.polygon([at(ax, az)] + [at(*p) for p in pts], fill=(255, 240, 120, 70), outline=(255, 240, 120, 160))
        x, y = at(g['x'], g['z'])
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(160, 160, 255) if w['kind'] == 'camera' else (220, 60, 60))
    if len(path) > 1:
        d.line([at(*p) for p in path], fill=(255, 140, 0, 160), width=2)
    x, y = at(sim.th['x'], sim.th['z'])
    d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(120, 70, 0) if sim.th['hidden'] else (255, 140, 0))
    d.text((6, 4), f't = {sim.clock} ({sim.clock / 60:.1f} s)', fill=(255, 255, 255))
    return im


