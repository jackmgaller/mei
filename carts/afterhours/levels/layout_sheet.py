"""Layout sheets for a stage (the owner's gate: rough sketches before a stage is built): a section
of the whole place, every room a box at its floor's height with the route's legs between them,
and a plan of each room from its play file: walls and cover, the way in and out, the watchers
with their routes or sweeps and rough cones, and the thief's intended path (the solution's plan,
played on the rules' model). Boxes and lines, labelled; no art. Needs Pillow.

A stage's `sketch.py` (levels/station/sketch.py, levels/tower/sketch.py) calls sheet().
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules_model as S  # noqa: E402
import planner as PL  # noqa: E402

FONTS = Path(__file__).resolve().parents[3] / 'tools' / 'fonts'
BG = (246, 244, 238)
INK = (40, 42, 48)
SOFT = (120, 124, 132)
FLOOR = (226, 222, 212)
WALL = (70, 74, 84)
LOW = (196, 168, 124)
GLASS = (120, 186, 220)
HIDE = (70, 110, 190)
CONE = (250, 210, 70)
GUARD = (210, 60, 50)
CAMERA = (110, 90, 200)
THIEF = (240, 130, 20)
THIEF_2 = (190, 60, 170)                     # a room's second visit
DOOR = (60, 160, 90)
NEW = (220, 90, 40)
OLD = (80, 120, 160)


def font(size, bold=False):
    name = 'Figtree-Bold.ttf' if bold else 'Figtree-Medium.ttf'
    return ImageFont.truetype(str(FONTS / name), size)


def wrap(d, text, f, width):
    """`text` broken into lines no wider than `width` pixels."""
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and d.textlength(t, font=f) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def path_of(play, plan, door=None):
    """The thief's positions, tick by tick, with the plan played on the model (from the spawn of
    the door he comes in by, in a room of doors)."""
    sim = S.Sim(play=play, door=door)
    r = PL.play(plan, sim)
    sim = S.Sim(play=play, door=door)
    pts = [(sim.th['x'], sim.th['z'])]
    for pad, sx, sy in r['inputs']:
        sim.tick(pad, sx, sy)
        pts.append((sim.th['x'], sim.th['z']))
    return pts, r['result']


def wedge(d, cx, cz, a0, a1, rng, fill, outline=None, at=None):
    pts = [at(cx, cz)]
    n = max(2, int(abs(a1 - a0) / 6) + 2)
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append(at(cx + math.sin(a) * rng, cz + math.cos(a) * rng))
    d.polygon(pts, fill=fill, outline=outline)


def arrow(d, p0, p1, col, w=2, head=8):
    d.line([p0, p1], fill=col, width=w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        d.line([p1, (p1[0] - head * math.cos(a + s * 0.45), p1[1] - head * math.sin(a + s * 0.45))], fill=col, width=w)


def room_plan(room, px=26):
    """One room's plan as an image. room: dict(label, play (a path or the play itself), status
    ('dressed' or 'new'), note (a line), and plan (a room of a line) or legs [(leg number, plan,
    the door he comes in by)] with doors {door id: its label} (a room of doors))."""
    play = room['play'] if isinstance(room['play'], dict) else json.loads(Path(room['play']).read_text())
    legs = room.get('legs') or [(None, room['plan'], None)]
    ents = {e['id']: e for e in play['entities']}
    rm = next(e for e in play['entities'] if e['type'] == 'room')
    sx, sz = rm['params']['size'][0], rm['params']['size'][2]
    cx, cz = rm['position'][0], rm['position'][2]
    status = room.get('status', 'dressed')
    tag = 'NEW (greybox)' if status == 'new' else 'existing, dressed'
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    title_w = probe.textlength(room['label'], font=font(20, True))
    tag_w = probe.textlength(tag, font=font(14, True))
    pad, right = 18, 90                       # room on the right for the watchers' labels
    W = int(max(sx * px + 2 * pad + right, title_w + tag_w + 3 * pad + 14, 420))
    note = wrap(probe, room.get('note', ''), font(13), W - 2 * pad)
    what = ('thief\'s path (orange): the solution, {s} s' if legs[0][0] is None else
            'thief\'s path: {s}' if len(legs) == 1 else 'thief\'s paths: {s}')
    foot = wrap(probe, what + f'; cones (yellow) at full reach, cut to the room; grid 1 m = {px} px', font(12),
                W - 2 * pad - 60)
    head = 40 + 18 * len(note) + 6
    H = int(sz * px + 2 * pad + head + 18 * len(foot) + 6)
    ox, oz = cx - sx / 2, cz + sz / 2
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im, 'RGBA')

    def at(x, z):
        return (pad + (x - ox) * px, head + pad + (oz - z) * px)
    d.text((pad, 8), room['label'], font=font(20, True), fill=INK)
    bx = pad + title_w + 14
    d.rounded_rectangle([bx, 10, bx + tag_w + 14, 32], 6, fill=NEW if status == 'new' else OLD)
    d.text((bx + 7, 12), tag, font=font(14, True), fill=(255, 255, 255))
    for k, line in enumerate(note):
        d.text((pad, 38 + 18 * k), line, font=font(13), fill=SOFT)
    # cones go on their own layer, cut to the room's floor
    cones = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dc = ImageDraw.Draw(cones, 'RGBA')
    d.rectangle([at(cx - sx / 2, cz + sz / 2), at(cx + sx / 2, cz - sz / 2)], fill=FLOOR)
    for e in play['entities']:
        if e['type'] == 'hide_spot':
            b = S.Box(e['position'][0], e['position'][2], e['params']['size'][0], e['params']['size'][2])
            d.polygon([at(*p) for p in b.corners()], fill=(*HIDE, 60), outline=HIDE)
    def walls(blocking_only=False):
        for e in play['entities']:
            if e['type'] != 'wall':
                continue
            p = e['params']
            if blocking_only and not p.get('blocks', True):
                continue
            b = S.Box(e['position'][0], e['position'][2], p['size'][0], p['size'][2])
            glassy = any(k in e['id'] for k in ('glass', 'window', 'tank', 'cube', 'column'))
            col = WALL if p.get('blocks', True) else (GLASS if glassy else LOW)
            d.polygon([at(*q) for q in b.corners()], fill=col)
    walls()
    # watchers: sweeps and routes
    wps = {e['id']: e for e in play['entities'] if e['type'] == 'waypoint'}
    marks = []
    casting = S.Sim(play=play, door=legs[0][2])      # the wall map, for beams cast against it
    for e in play['entities']:
        if e['type'] != 'guard':
            continue
        p = e['params']
        gx, gz = e['position'][0], e['position'][2]
        rng, half = p.get('sight', 6), p.get('fov', 60) / 2
        if p['kind'] in ('posted', 'camera'):
            a0, a1 = sorted((p.get('look_a', 0), p.get('look_b', 0)))
            if 2 * half <= 20 and a1 - a0 > 4 * half:
                # a narrow beam swept wide: the beam at a few of its headings, cast against what
                # blocks it (its shadows are the room), and the sweep's reach as a line
                n = max(2, int((a1 - a0) / 15))
                for k in range(n + 1):
                    h = a0 + (a1 - a0) * k / n
                    _, _, pts = S.fan_cast(gx, gz, h * S.DEG, half * S.DEG, rng, casting.segs)
                    dc.polygon([at(gx, gz)] + [at(*q) for q in pts], fill=(*CONE, 75), outline=(*CONE, 200))
                q = [at(gx + math.sin(math.radians(a)) * rng, gz + math.cos(math.radians(a)) * rng)
                     for a in range(int(a0 - half), int(a1 + half) + 1, 3)]
                dc.line(q, fill=(*CONE, 230), width=2)
            else:
                wedge(dc, gx, gz, a0 - half, a1 + half, rng, (*CONE, 90), (*CONE, 220), at=at)
            col = CAMERA if p['kind'] == 'camera' else GUARD
            x, y = at(gx, gz)
            lab = 'camera' if p['kind'] == 'camera' else 'posted'
            marks.append((x, y, col, f'{lab} {p.get("look_a", 0):g}-{p.get("look_b", 0):g}°'))
        else:
            route, wid = [], p.get('route')
            seen = set()
            while wid and wid not in seen and wid in wps:
                seen.add(wid)
                route.append(wps[wid])
                wid = wps[wid]['params'].get('next')
            pts = [at(w['position'][0], w['position'][2]) for w in route]
            if len(pts) > 1:
                loop = pts + [pts[0]]
                for k in range(len(loop) - 1):
                    arrow(d, loop[k], ((loop[k][0] + loop[k + 1][0]) / 2, (loop[k][1] + loop[k + 1][1]) / 2), GUARD, 2)
                    d.line([loop[k], loop[k + 1]], fill=(*GUARD, 150), width=2)
            for w in route:
                if w['params'].get('wait', 0) > 0:
                    x, y = at(w['position'][0], w['position'][2])
                    d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=GUARD, width=2)
            yaw = e.get('yaw', 0)
            wedge(dc, gx, gz, yaw - half, yaw + half, rng, (*CONE, 80), (*CONE, 200), at=at)
            x, y = at(gx, gz)
            marks.append((x, y, GUARD, f'patrol {p.get("speed", 1.2):g} m/s'))
    fx0, fy0 = at(cx - sx / 2, cz + sz / 2)
    fx1, fy1 = at(cx + sx / 2, cz - sz / 2)
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rectangle([fx0, fy0, fx1, fy1], fill=255)
    cut = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cut.paste(cones, (0, 0), mask)
    im.paste(cut, (0, 0), cut)
    d = ImageDraw.Draw(im, 'RGBA')
    walls(True)                               # over the cones: what blocks sight (low and glass things do not)
    for x, y, col, text in marks:             # the watchers again, over their cones
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col)
        d.text((x + 9, y - 9), text, font=font(12), fill=col)
    # in and out
    labels = room.get('doors')
    if labels is None:                     # a room of a line: its spawn and its exit
        sp = ents.get(rm['params'].get('entry'))
        if sp:
            x, y = at(sp['position'][0], sp['position'][2])
            d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=DOOR, width=3)
            d.text((x - 6, y + 9), 'in', font=font(13, True), fill=DOOR)
        ex = ents.get(rm['params'].get('exit'))
        if ex:
            b = S.Box(ex['position'][0], ex['position'][2], ex['params']['size'][0], ex['params']['size'][2])
            d.polygon([at(*q) for q in b.corners()], fill=DOOR)
            x, y = at(ex['position'][0], ex['position'][2])
            d.text((x - 30, y + 10), 'out', font=font(13, True), fill=DOOR)
    else:                                  # a room of doors: every door, labelled
        for e in play['entities']:
            if e['type'] != 'door':
                continue
            sz_ = e['params'].get('size', [1.2, 2.2, 0.4])
            b = S.Box(e['position'][0], e['position'][2], sz_[0], sz_[2], yaw=e.get('yaw', 0) * S.DEG)
            d.polygon([at(*q) for q in b.corners()], fill=DOOR)
            text = labels.get(e['id'], '')
            if not text:
                continue
            # the label just inside the room from the door
            dx, dz = cx - e['position'][0], cz - e['position'][2]
            n = max(1e-6, math.hypot(dx, dz))
            lx, lz = e['position'][0] + dx / n * 1.1, e['position'][2] + dz / n * 0.9
            x, y = at(lx, lz)
            f = font(11, True)
            tw = d.textlength(text, font=f)
            x = min(max(x - tw / 2, at(cx - sx / 2, 0)[0] + 4), at(cx + sx / 2, 0)[0] - tw - 4)
            d.rounded_rectangle([x - 3, y - 8, x + tw + 3, y + 8], 4, fill=(255, 255, 255, 210))
            d.text((x, y), text, font=f, fill=DOOR, anchor='lm')
    # the thief's paths
    times = []
    for k, (n, plan, door) in enumerate(legs):
        col = THIEF if k == 0 else THIEF_2
        pts, res = path_of(play, plan, door)
        line = [at(*q) for q in pts[::4]]
        if len(line) > 1:
            d.line(line, fill=col, width=3)
            arrow(d, line[max(0, len(line) - 6)], line[-1], col, 3, 9)
        if n is not None:
            x, y = line[0]
            d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=col)
            d.text((x, y), str(n), font=font(13, True), fill=(255, 255, 255), anchor='mm')
            times.append(f'leg {n}' + (f' ({"orange" if k == 0 else "purple"})' if len(legs) > 1 else ' (orange)')
                         + f', {(res[1] + 1) / 60 if res else 0:.0f} s')
        else:
            times.append(f'{(res[1] + 1) / 60 if res else 0:.0f}')
    for k, line in enumerate(foot):
        d.text((pad, H - 18 * len(foot) - 4 + 18 * k), line.replace('{s}', ', '.join(times)), font=font(12), fill=SOFT)
    return im


def section(rooms, title, width):
    """The stage's section: each room a box at its floor's height (tall gaps closed up), joined
    in the order played, legs numbered."""
    pad, head = 30, 70
    xs, total = [], 0.0
    for r in rooms:
        xs.append(total)
        total += r['width'] + 4
    scale = (width - 2 * pad) / total
    ys = [r['floor'] for r in rooms]
    lifted, lift = [], 0.0
    for k, y in enumerate(ys):
        if k:
            rise = y - ys[k - 1]
            lift += max(-9, min(9, rise)) - rise
        lifted.append(y + lift)
    lo, hi = min(lifted), max(lifted)
    vs = min(scale, 240 / max(1.0, hi - lo))
    BOX = 50                                  # a room's box, px tall (not to scale)
    head += BOX + 10
    H = int(head + (hi - lo) * vs + 60)
    im = Image.new('RGB', (width, H), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    d.text((pad, 10), title, font=font(26, True), fill=INK)
    d.text((pad, 42), 'Section through the whole place, rooms at their floors\' heights (long rises closed up); '
           'the legs of the run numbered in order. Blue: existing dressed rooms; orange: new rooms.',
           font=font(14), fill=SOFT)

    def at(x, y):
        return (pad + x * scale, head + (hi - y) * vs)
    if lo < 0 < hi:
        y0 = at(0, 0)[1]
        d.line([(pad - 10, y0), (width - pad + 10, y0)], fill=(*SOFT, 120), width=1)
        d.text((width - pad - 70, y0 - 18), 'street', font=font(12), fill=SOFT)
    boxes = []
    for k, r in enumerate(rooms):
        x1, y1 = at(xs[k] + r['width'], lifted[k])
        x0, y0 = at(xs[k], lifted[k])[0], y1 - BOX
        col = NEW if r.get('status') == 'new' else OLD
        d.rectangle([x0, y0, x1, y1], fill=(*col, 50), outline=col, width=3)
        d.text((x0 + 6, y0 + 4), r['label'], font=font(15, True), fill=INK)
        st = r['storey']
        d.text((x0 + 6, y0 + 24), (f'{st}F' if st > 0 else f'B{-st}') + f', floor {r["floor"]:g} m', font=font(12), fill=SOFT)
        boxes.append((x0, y0, x1, y1))
    for k in range(len(rooms) - 1):
        a, b = boxes[k], boxes[k + 1]
        p0 = (a[2] + 2, (a[1] + a[3]) / 2)
        p1 = (b[0] - 2, (b[1] + b[3]) / 2)
        arrow(d, p0, p1, THIEF, 3, 10)
    for k, bx in enumerate(boxes):
        cx, cy = bx[2] - 20, (bx[1] + bx[3]) / 2
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=THIEF)
        d.text((cx, cy), str(k + 1), font=font(15, True), fill=(255, 255, 255), anchor='mm')
    a, b = boxes[0], boxes[-1]
    d.text((a[0], a[3] + 6), 'in: ' + rooms[0].get('in', ''), font=font(13), fill=DOOR)
    tw = d.textlength('out: ' + rooms[-1].get('out', ''), font=font(13))
    d.text((b[2] - tw, b[3] + 6), 'out: ' + rooms[-1].get('out', ''), font=font(13), fill=DOOR)
    return im


def building_section(title, b, width):
    """A stage that is one building, in section: its storeys, the shafts that join them (lifts,
    stairs), the rooms played on their floors, and the route through them, legs numbered. b:
    dict(width (m), storeys [(label, floor y)], shafts [(label, x0, x1, y0, y1, colour, note)],
    rooms [(label, sub, x0, x1, floor y, status)], route [[(x, y), ...] per colour run, with the
    leg numbers [(n, x, y, colour)] in `legs`], notes [(x, y, text)]). x and y in metres."""
    pad, head, left = 30, 74, 64
    top = max(y for _, y in b['storeys']) + 6.5
    sx = (width - 2 * pad - left - 120) / b['width']
    sy = 11.0
    H = int(head + top * sy + 70)
    im = Image.new('RGB', (width, H), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    d.text((pad, 10), title, font=font(26, True), fill=INK)
    d.text((pad, 42), 'Section through the building (schematic across, storeys to scale): the rooms played on their '
           'floors, the lifts and stairs between them, the route\'s legs numbered in order. Blue: existing dressed '
           'rooms; orange: new rooms.', font=font(14), fill=SOFT)

    def at(x, y):
        return (pad + left + x * sx, head + (top - y) * sy)
    # the storeys
    x0, _ = at(0, 0)
    x1, _ = at(b['width'], 0)
    for label, y in b['storeys']:
        _, yy = at(0, y)
        d.line([(x0, yy), (x1, yy)], fill=(*SOFT, 90), width=1)
        d.text((pad, yy - 16), label, font=font(12, True), fill=SOFT)
    _, yg = at(0, 0)
    d.line([(pad, yg), (width - pad, yg)], fill=INK, width=2)
    d.text((pad + left - 4, yg + 4), 'street', font=font(12), fill=SOFT)
    _, yt = at(0, top - 1.0)
    d.rectangle([x0, yt, x1, yg], outline=(*WALL, 160), width=2)
    # the rooms, the shafts through them, then the rooms' names over both
    for label, sub, rx0, rx1, y, status in b['rooms']:
        col = NEW if status == 'new' else OLD
        a, bb = at(rx0, y + 3.6), at(rx1, y)
        d.rectangle([a[0] + 1, a[1], bb[0] - 1, bb[1] - 1], fill=(*col, 45), outline=col, width=3)
    for label, sx0, sx1, y0, y1, col, note in b['shafts']:
        a, bb = at(sx0, y1), at(sx1, y0)
        d.rectangle([a[0], a[1], bb[0], bb[1]], fill=(*col, 70), outline=col, width=2)
        if note:
            d.text(((a[0] + bb[0]) / 2, a[1] - 3), note, font=font(11, True), fill=col, anchor='md')
    for label, sub, rx0, rx1, y, status in b['rooms']:      # each room's name just over it
        a = at(rx0 + b.get('label_dx', {}).get(label, 0.0), y + 3.6)
        w1 = d.textlength(label, font=font(14, True))
        w = w1 + 8 + d.textlength(sub, font=font(12))
        d.rounded_rectangle([a[0] + 4, a[1] - 21, a[0] + 12 + w, a[1] - 2], 4, fill=(*BG, 230))
        d.text((a[0] + 8, a[1] - 4), label, font=font(14, True), fill=INK, anchor='ls')
        d.text((a[0] + 16 + w1, a[1] - 4), sub, font=font(12), fill=SOFT, anchor='ls')
    for x, y, text, col in b.get('marks', []):
        d.text(at(x, y), text, font=font(11, True), fill=col, anchor='mm')
    # the route
    for pts, col in b['route']:
        q = [at(*p) for p in pts]
        for k in range(len(q) - 1):
            d.line([q[k], q[k + 1]], fill=col, width=3)
        for k in range(len(q) - 1):
            mx, my = (q[k][0] + q[k + 1][0]) / 2, (q[k][1] + q[k + 1][1]) / 2
            if math.hypot(q[k + 1][0] - q[k][0], q[k + 1][1] - q[k][1]) > 40:
                arrow(d, q[k], (mx, my), col, 3, 9)
        arrow(d, q[-2], q[-1], col, 3, 10)
    for n, x, y, col in b['legs']:
        cx, cy = at(x, y)
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=col)
        d.text((cx, cy), str(n), font=font(15, True), fill=(255, 255, 255), anchor='mm')
    for x, y, text, col in b.get('notes', []):
        d.text(at(x, y), text, font=font(12), fill=col)
    return im


def sheet(title, rooms, out, footer=(), width=1800, building=None):
    """rooms: [dict(label, play, status, note, and plan (a room of a line: floor, storey, width
    (m, for the section), in, out) or legs and doors (a room of doors, room_plan())]. building: a
    stage that is one building is drawn in section by building_section() from it."""
    sec = building_section(title, building, width) if building else section(rooms, title, width)
    plans = [room_plan(r) for r in rooms]
    cols = 2
    col_w = (width - 60) // cols
    rows = []
    for k in range(0, len(plans), cols):
        rows.append(plans[k:k + cols])
    scaled_rows = []
    for row in rows:
        imgs = []
        for p in row:
            s = min(1.0, col_w / p.width)
            imgs.append(p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS) if s < 1 else p)
        scaled_rows.append(imgs)
    H = sec.height + sum(max(i.height for i in r) + 20 for r in scaled_rows) + 40 + 22 * len(footer)
    im = Image.new('RGB', (width, H), BG)
    im.paste(sec, (0, 0))
    y = sec.height + 10
    for r in scaled_rows:
        x = 30
        for p in r:
            im.paste(p, (x, y))
            x += col_w
        y += max(i.height for i in r) + 20
    d = ImageDraw.Draw(im)
    for k, line in enumerate(footer):
        d.text((30, y + 22 * k), line, font=font(14), fill=INK)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print('wrote', out)
