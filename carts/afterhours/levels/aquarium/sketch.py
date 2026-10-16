#!/usr/bin/env python3
"""The aquarium stage's layout sheet: a section of the whole aquarium and a plan of every room
on every level it is played on, rough and labelled, for the owner to judge the layout before
the rooms are built. Reads the rooms' descriptions (rooms/aq_*/make_*.py's ROOM and SKETCH, the
ocean gallery's play file) and draws with Pillow, text in Figtree from tools/fonts/.

    python3 carts/afterhours/levels/aquarium/sketch.py [-o levels/aquarium/sketch.png]

Writes sketch.png beside itself (2,400 px wide).
"""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
REPO = CART.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CART / 'levels'))
sys.path.insert(0, str(HERE))
import aqroom  # noqa: E402

FONT = REPO / 'tools/fonts/Figtree-SemiBold.ttf'
FONT_B = REPO / 'tools/fonts/Figtree-Bold.ttf'


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_B if bold else FONT), size)


def load(name):
    p = CART / 'rooms' / name / f'make_{name}.py'
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# The rooms in the section's order: (folder or 'ocean', floor y, label)
ROOMS = [('aq_hall', 0.0, '1F'), ('aq_great', 0.0, '1F'), ('aq_jelly', 0.0, '1F'), ('ocean', 0.0, '1F'),
         ('aq_quar', 0.0, '1F'), ('aq_plant', -4.0, 'B1'), ('aq_kitchen', 4.0, '2F'), ('aq_tops', 4.0, '2F')]
# The legs: (room, level)
LEGS = [('aq_hall', 0), ('aq_great', 0), ('aq_jelly', 0), ('ocean', 0), ('aq_quar', 0), ('aq_plant', 0),
        ('aq_kitchen', 0), ('aq_tops', 0), ('aq_great', 1), ('aq_hall', 1)]
TITLES = {'aq_hall': 'The entrance hall', 'aq_great': 'The great tank', 'aq_jelly': 'The jellyfish gallery',
          'ocean': 'The ocean gallery (the sketch)', 'aq_quar': 'Quarantine', 'aq_plant': 'The life-support plant',
          'aq_kitchen': 'The fish kitchen', 'aq_tops': 'The tank tops'}
TEACH = ['the dark: unlit watchers see only in light', 'torches: a lamp sees its whole cone',
         'lights on a cycle', 'glass (the tower\'s idea again)', 'dark, torch and timers together',
         'water: walkways, sight crosses water', 'lit; buckets are noise, the freezer hides',
         'walkways over water in the dark', 'two levels: the catwalk over leg 1',
         'everything: dark, torch, hiding; the way out']

BG = (246, 244, 238)
INK = (30, 32, 40)
COL = {
    'floor': (214, 212, 204), 'floor_dark': (150, 156, 172), 'wall': (60, 62, 70), 'glass': (120, 190, 220),
    'low': (170, 140, 104), 'seat': (170, 140, 104), 'water': (70, 120, 170), 'machine': (88, 104, 128),
    'pillar': (60, 62, 70), 'block': (80, 82, 92), 'air': (236, 236, 240), 'walk': (176, 168, 150),
    'light': (255, 226, 90), 'door': (40, 170, 90), 'path': (240, 120, 20), 'guard': (210, 50, 50),
    'camera': (130, 70, 190), 'hide': (60, 100, 200), 'fragile': (230, 140, 60),
}


class Room:
    def __init__(self, name):
        self.name = name
        if name == 'ocean':
            m = importlib.util.spec_from_file_location('ocean', HERE / 'ocean' / 'make_ocean_play.py')
            mod = importlib.util.module_from_spec(m)
            m.loader.exec_module(mod)
            self.ents = mod.play()['entities']
            self.d = None
            self.sketch = mod.SKETCH
            room = self.ents[0]
            sx, _, sz = room['params']['size']
            cz = room['position'][2]
            self.box = (-sx / 2, cz - sz / 2, sx / 2, cz + sz / 2)
            self.inner = (-5.8, -2.9, 5.8, 2.9)
            self.upper = None
            self.dark = False
        else:
            mod = load(name)
            self.d = mod.ROOM
            self.sketch = getattr(mod, 'SKETCH', {})
            self.ents = aqroom.play_entities(self.d)
            X0, X1 = self.d['x']
            Z0, Z1 = self.d['z']
            self.inner = (X0, Z0, X1, Z1)
            self.box = (X0 - 0.25, Z0 - 0.25, X1 + 0.25, Z1 + 0.25)
            self.upper = self.d.get('upper')
            self.dark = self.d.get('dark', False)
        self.byid = {e['id']: e for e in self.ents}

    def kind_of(self, wall_id):
        """The prop kind a wall entity was made from (for its colour)."""
        if self.d is None:
            p = self.byid[wall_id]['params']
            if wall_id.startswith('ao_glass'):
                return 'glass'
            return 'wall' if p.get('blocks', True) else 'low'
        P = self.d['prefix']
        for key in ('props', 'upper_props'):
            for prop in self.d.get(key, []):
                if P + 'wall_' + prop[0] == wall_id:
                    return prop[1]
        if '_air_' in wall_id:
            return 'air'
        return 'wall'


def lvl(e):
    return e['params'].get('level', 0)


def draw_fan(d, at, x, z, head, half, rng, fill, outline, width=2, dotted=False):
    pts = [at(x, z)]
    for k in range(13):
        a = head - half + 2 * half * k / 12
        pts.append(at(x + math.sin(a) * rng, z + math.cos(a) * rng))
    if fill:
        d.polygon(pts, fill=fill)
    if dotted:
        for i in range(len(pts)):
            p0, p1 = pts[i], pts[(i + 1) % len(pts)]
            n = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 8))
            for k in range(0, n, 2):
                a0 = (p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n)
                a1 = (p0[0] + (p1[0] - p0[0]) * (k + 1) / n, p0[1] + (p1[1] - p0[1]) * (k + 1) / n)
                d.line([a0, a1], fill=outline, width=width)
    else:
        d.line(pts + [pts[0]], fill=outline, width=width)


def arrow(d, p0, p1, col, width=3, head=10):
    d.line([p0, p1], fill=col, width=width)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        d.line([p1, (p1[0] - head * math.cos(a + s * 0.45), p1[1] - head * math.sin(a + s * 0.45))], fill=col, width=width)


def plan(room, level, leg, px=40):
    """One room on one level, as a picture."""
    bx0, bz0, bx1, bz1 = room.box
    margin = 1.6
    w = int((bx1 - bx0 + 2 * margin) * px)
    h = int((bz1 - bz0 + 2 * margin) * px) + 70
    im = Image.new('RGB', (w, h), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    ox, oz = bx0 - margin, bz1 + margin

    def at(x, z):
        return ((x - ox) * px, (oz - z) * px + 70)
    title = f'Leg {leg}: {TITLES[room.name]}' + (', the upper level (+3.2 m)' if level == 1 else
                                                    (', the floor' if room.upper else ''))
    d.text((12, 6), title, font=font(26, True), fill=INK)
    d.text((12, 40), TEACH[leg] + ('   (dark room)' if room.dark else '   (lit room)'), font=font(18), fill=(90, 90, 100))
    X0, Z0, X1, Z1 = room.inner
    d.rectangle([*at(X0, Z1), *at(X1, Z0)], fill=COL['floor_dark'] if room.dark else COL['floor'])
    # the other level, faint
    other = [e for e in room.ents if e['type'] == 'wall' and lvl(e) != level]
    mine = [e for e in room.ents if e['type'] == 'wall' and lvl(e) == level]

    def rect(e):
        x, _, z = e['position']
        sx, _, sz = e['params']['size']
        return (x - sx / 2, z - sz / 2, x + sx / 2, z + sz / 2)
    if level == 1:
        for e in other:
            if room.kind_of(e['id']) in ('air',):
                continue
            q = rect(e)
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=(120, 120, 130, 60))
        for q in room.d.get('walks', []):
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=COL['walk'], outline=(110, 100, 80), width=2)
    # lights
    for e in room.ents:
        if e['type'] == 'light' and lvl(e) == level:
            q = rect(e)
            timed = 'period' in e['params']
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=COL['light'] + ((70,) if timed else (120,)),
                        outline=(200, 160, 0), width=3 if timed else 1)
            if timed:
                p = e['params']
                cx, cz = (q[0] + q[2]) / 2, q[3]
                d.text((at(cx, cz)[0] - 52, at(cx, cz)[1] + 4), f'on {p["on"] / 60:.0f}s of {p["period"] / 60:.0f}s, +{p["offset"] / 60:.0f}s',
                       font=font(14), fill=(120, 90, 0))
    # walls
    for e in mine:
        k = room.kind_of(e['id'])
        q = rect(e)
        if k == 'air':
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=(240, 240, 246, 150), outline=(190, 190, 200))
            continue
        c = COL.get(k, COL['wall'])
        if k == 'water':
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=c + (200,), outline=(40, 80, 130))
        elif k == 'glass':
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=c + (150,), outline=(40, 120, 170), width=2)
        else:
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], fill=c)
    # hiding places, fragile things
    for e in room.ents:
        if lvl(e) != level:
            continue
        if e['type'] == 'hide_spot':
            q = rect(e)
            d.rectangle([*at(q[0], q[3]), *at(q[2], q[1])], outline=COL['hide'], width=3)
            d.text(at(q[0], q[1]), 'hide', font=font(14), fill=COL['hide'])
        if e['type'] == 'fragile':
            x, _, z = e['position']
            rr = e['params']['radius'] * px
            cx, cy = at(x, z)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=COL['fragile'])
    # doors
    names = {'ah': 'entrance hall', 'ag': 'great tank', 'aj': 'jellyfish', 'ao': 'ocean gallery', 'qt': 'quarantine',
             'ap': 'plant', 'ak': 'kitchen', 'at': 'tank tops'}
    for e in room.ents:
        if e['type'] != 'door' or lvl(e) != level:
            continue
        x, _, z = e['position']
        sx, _, sz = e['params']['size']
        yaw = e.get('yaw', 0)
        if yaw in (90, 270):
            sx, sz = sz, sx
        d.rectangle([*at(x - sx / 2, z + sz / 2), *at(x + sx / 2, z - sz / 2)], fill=COL['door'])
        p = e['params']
        lab = 'OUT (end)' if p.get('end') else ('from ' + names[p['to'][:2]] if p.get('to') else 'IN (start)')
        if p.get('to'):
            lab = '<-> ' + names[p['to'][:2]] + (' (upper)' if p['to'] in ('ah_door_catwalk', 'ag_door_hall_up', 'ag_door_tops') else '')
        tx, ty = at(x, z)
        f = font(15, True)
        tw = d.textlength(lab, font=f)
        tx = min(max(tx - tw / 2, 2), w - tw - 2)
        ty = ty + (14 if yaw == 180 or (z > room.inner[3] - 0.1) else -32) if yaw in (0, 180) else ty - 30
        d.text((tx, ty), lab, font=f, fill=(20, 110, 60))
    # watchers
    wps = {e['id']: e for e in room.ents if e['type'] == 'waypoint'}
    for e in room.ents:
        if e['type'] != 'guard':
            continue
        p = e['params']
        on = lvl(e) == level
        faint = not on
        x, _, z = e['position']
        torch = p.get('torch', False)
        dark_eyed = room.dark and not torch
        fan_fill = None if faint else ((255, 210, 60, 70) if not dark_eyed else None)
        fan_line = (150, 150, 150) if faint else ((200, 140, 0) if not dark_eyed else (120, 100, 40))
        half = p.get('fov', 60) * math.pi / 360
        rng = p.get('sight', 6)
        col = COL['camera'] if p['kind'] == 'camera' else COL['guard']
        if faint:
            col = (170, 170, 175)
        if p['kind'] == 'patrol':
            route = []
            wid = p['route']
            seen = set()
            while wid and wid not in seen:
                seen.add(wid)
                route.append(wps[wid])
                wid = wps[wid]['params'].get('next')
            pts = [at(w['position'][0], w['position'][2]) for w in route]
            if len(pts) > 1:
                d.line(pts + [pts[0]], fill=col + ((200,) if not faint else (90,)), width=3)
                for a, b in zip(pts, pts[1:] + [pts[0]]):
                    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    arrow(d, a, mid, col, width=3, head=12)
            for wpt in route:
                if wpt['params'].get('wait'):
                    lx, lz = wpt['position'][0], wpt['position'][2]
                    lk = wpt['params'].get('look', 0) * math.pi / 180
                    if on:
                        draw_fan(d, at, lx, lz, lk, half, rng, fan_fill, fan_line, 2, dotted=dark_eyed)
            # his first leg's look
            if on and route:
                h0 = math.atan2(route[0]['position'][0] - x, route[0]['position'][2] - z)
                draw_fan(d, at, x, z, h0, half, rng, fan_fill, fan_line, 2, dotted=dark_eyed)
        else:
            if on:
                for look in {p['look_a'], p['look_b']}:
                    draw_fan(d, at, x, z, look * math.pi / 180, half, rng, fan_fill, fan_line, 2, dotted=dark_eyed)
        cx, cy = at(x, z)
        r0 = 9
        if p['kind'] == 'camera':
            d.rectangle([cx - r0, cy - r0, cx + r0, cy + r0], fill=col)
        else:
            d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=col)
        if on:
            short = e['id'].split('_', 2)[-1]
            lab = short + (' (torch)' if torch else '') + (f'  {p["look_a"]}°-{p["look_b"]}°' if p['kind'] != 'patrol' else '')
            d.text((cx + 12, cy - 8), lab, font=font(15, True), fill=col)
    # the thief's way
    path = room.sketch.get(leg)
    if path:
        pts = [at(q[0], q[1]) for q in path]
        d.line(pts, fill=COL['path'], width=5, joint='curve')
        arrow(d, pts[-2], pts[-1], COL['path'], width=5, head=16)
        cx, cy = pts[0]
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=COL['path'])
        for q in path:
            if len(q) > 2:
                cx, cy = at(q[0], q[1])
                d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], outline=COL['path'], width=4)
                d.text((cx + 14, cy + 4), q[2], font=font(15, True), fill=(200, 90, 0))
    # the camera's side
    d.text((12, h - 24), 'camera side (front wall cut at 1 m)', font=font(14), fill=(120, 120, 130))
    d.text((w - 70, h - 24), f'{px} px/m', font=font(14), fill=(120, 120, 130))
    return im


def section(rooms, wpx=2400):
    """Every room as a box at its floor's height, the legs in order."""
    py = 26
    gap = 2.5
    total = sum(r.box[2] - r.box[0] for r in rooms) + gap * (len(rooms) - 1)
    pxm = (wpx - 120) / total
    h = 640
    im = Image.new('RGB', (wpx, h), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    d.text((20, 10), 'The aquarium: the section (rooms side by side as the world keeps them, each at its floor)',
           font=font(30, True), fill=INK)
    base = 330

    def Y(y):
        return base - y * py
    for y, lab in ((-4, 'B1'), (0, '1F'), (4, '2F'), (8, '3F')):
        d.line([(60, Y(y)), (wpx - 20, Y(y))], fill=(200, 200, 205), width=1)
        d.text((14, Y(y) - 12), lab, font=font(18, True), fill=(130, 130, 140))
    x = 70
    where = {}
    for r, (name, fy, lab) in zip(rooms, ROOMS):
        wdt = (r.box[2] - r.box[0]) * pxm
        top = fy + (r.upper or 0) + 2.4
        d.rectangle([x, Y(top), x + wdt, Y(fy)], fill=(150, 156, 172) if r.dark else (214, 212, 204), outline=INK, width=2)
        d.rectangle([x, Y(fy), x + wdt, Y(fy) + 6], fill=INK)
        if r.upper:
            d.rectangle([x, Y(fy + r.upper), x + wdt, Y(fy + r.upper) + 5], fill=(120, 100, 70))
        d.text((x + 6, Y(top) - 26), TITLES[name].replace(' (the sketch)', ''), font=font(17, True), fill=INK)
        d.text((x + 6, Y(fy) + 10), f'{lab}, {r.box[2] - r.box[0]:.0f} x {r.box[3] - r.box[1]:.1f} m' + ('  dark' if r.dark else ''),
               font=font(15), fill=(90, 90, 100))
        where[name] = (x, wdt, fy, r.upper)
        x += wdt + gap * pxm
    # the legs: a numbered disc on the level it is played, an arrow on to the next
    spots = []
    for k, (name, level) in enumerate(LEGS):
        x0, wdt, fy, up = where[name]
        y = fy + (up if level else 0) + 1.0
        cx = x0 + wdt * (0.5 if level == 0 else 0.62)
        spots.append((cx, Y(y)))
    for k in range(len(spots) - 1):
        a, b = spots[k], spots[k + 1]
        arrow(d, (a[0] + 18 * (1 if b[0] > a[0] else -1), a[1]), (b[0] - 18 * (1 if b[0] > a[0] else -1), b[1]),
              COL['path'], width=3, head=12)
    for k, (cx, cy) in enumerate(spots):
        d.ellipse([cx - 17, cy - 17, cx + 17, cy + 17], fill=COL['path'], outline=INK, width=2)
        t = str(k)
        f = font(20, True)
        d.text((cx - d.textlength(t, font=f) / 2, cy - 13), t, font=f, fill=(255, 255, 255))
    ly = 490
    d.text((20, ly), 'Legs, in order:', font=font(18, True), fill=INK)
    for k, (name, level) in enumerate(LEGS):
        col, row = k // 5, k % 5
        d.text((180 + col * 1100, ly + row * 26),
               f'{k}  {TITLES[name].replace(" (the sketch)", "")}{" (upper)" if level else ""}: {TEACH[k]}',
               font=font(17), fill=INK)
    return im


def legend(w=2400):
    im = Image.new('RGB', (w, 70), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    x = 20
    items = [('wall (blocks cones)', COL['wall'], 'r'), ('glass (cones pass)', COL['glass'], 'r'),
             ('low thing (cones pass)', COL['low'], 'r'), ('water (stops him, cones pass)', COL['water'], 'r'),
             ('machine (blocks)', COL['machine'], 'r'), ('catwalk / mezzanine', COL['walk'], 'r'),
             ('light (danger for unlit watchers)', COL['light'], 'r'), ('door', COL['door'], 'r'),
             ('guard', COL['guard'], 'c'), ('camera', COL['camera'], 's'), ('thief', COL['path'], 'c')]
    for lab, c, sh in items:
        if sh == 'r':
            d.rectangle([x, 22, x + 26, 44], fill=c)
        elif sh == 'c':
            d.ellipse([x + 2, 22, x + 24, 44], fill=c)
        else:
            d.rectangle([x + 3, 23, x + 23, 43], fill=c)
        d.text((x + 32, 22), lab, font=font(16), fill=INK)
        x += 44 + d.textlength(lab, font=font(16))
    d.text((20, 48), 'Fans: filled = sees everywhere (lit room, or a torch); dotted = an unlit watcher in a dark room (sees only where a light falls).'
           ' Thick outline on a light = it is on a cycle.', font=font(15), fill=(90, 90, 100))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', default=str(HERE / 'sketch.png'))
    args = ap.parse_args()
    rooms = {name: Room(name) for name, _, _ in ROOMS}
    sec = section([rooms[n] for n, _, _ in ROOMS])
    plans = [plan(rooms[name], level, k) for k, (name, level) in enumerate(LEGS)]
    W = 2400
    cols = 2
    rows = []
    for i in range(0, len(plans), cols):
        rows.append(plans[i:i + cols])
    hrows = [max(p.height for p in r) for r in rows]
    out = Image.new('RGB', (W, sec.height + 70 + sum(hrows) + 20 * len(rows)), BG)
    out.paste(sec, (0, 0))
    out.paste(legend(W), (0, sec.height))
    y = sec.height + 70
    for r, hh in zip(rows, hrows):
        x = 0
        for p in r:
            scale = min(1.0, (W / cols - 10) / p.width)
            q = p if scale == 1.0 else p.resize((int(p.width * scale), int(p.height * scale)), Image.LANCZOS)
            out.paste(q, (int(x + (W / cols - q.width) / 2), y))
            x += W / cols
        d = ImageDraw.Draw(out)
        d.line([(0, y + hh + 8), (W, y + hh + 8)], fill=(200, 200, 205), width=2)
        y += hh + 20
    out.save(args.o)
    print('wrote', args.o, out.size)


if __name__ == '__main__':
    main()
