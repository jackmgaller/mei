"""The explorer's outputs: the JSON report, the top-down map and the short text summary."""
import json
import math
from pathlib import Path

import numpy as np


def reach_grid(e):
    """Per column (nz, nx): the highest floor's height, the highest reachable floor's height
    (NaN where none)."""
    m = e.m
    F = m.floors
    n = m.nx * m.nz
    top = np.full(n, np.nan)
    rtop = np.full(n, np.nan)
    if len(F):
        last = np.r_[F.col[1:] != F.col[:-1], True]
        top[F.col[last]] = F.y[last]
        ok = np.isfinite(e.dist[:e.n_floor])
        c = F.col[ok]
        y = F.y[ok]
        # sorted by (col, y): the last reachable entry per column is its highest
        if len(c):
            lastr = np.r_[c[1:] != c[:-1], True]
            rtop[c[lastr]] = y[lastr]
    return top.reshape(m.nz, m.nx), rtop.reshape(m.nz, m.nx)


def draw_map(e, finds, confirmed, path, scale=2.0):
    """A top-down picture (north up) of the frame: the floors in grey by height, the reachable
    ones tinted green, and the finds marked."""
    from PIL import Image, ImageDraw
    m = e.m
    top, rtop = reach_grid(e)
    x0, z0, x1, z1 = m.frame
    pad = 8
    W = int((x1 - x0) * scale) + 2 * pad
    H = int((z1 - z0) * scale) + 2 * pad + 84
    img = Image.new('RGB', (W, H), (24, 24, 30))
    # sample the grid at the picture's pixels
    xs = x0 + (np.arange(W - 2 * pad) + 0.5) / scale
    zs = z1 - (np.arange(H - 2 * pad - 84) + 0.5) / scale
    ix = np.clip(np.rint((xs - m.ox) / m.grid).astype(int), 0, m.nx - 1)
    iz = np.clip(np.rint((zs - m.oz) / m.grid).astype(int), 0, m.nz - 1)
    t = top[np.ix_(iz, ix)]
    r = rtop[np.ix_(iz, ix)]
    finite = t[np.isfinite(t)]
    lo, hi = (float(np.percentile(finite, 1)), float(np.percentile(finite, 99))) if finite.size else (0, 1)
    k = np.clip((np.nan_to_num(t, nan=lo) - lo) / max(hi - lo, 1e-6), 0, 1)
    shade = (70 + 150 * k).astype(np.uint8)
    rgb = np.stack([shade, shade, shade], -1)
    reach = np.isfinite(r) & (np.abs(np.nan_to_num(r) - np.nan_to_num(t)) < 0.6)
    under = np.isfinite(r) & ~reach            # reachable, but under something higher
    kr = k[reach]
    rgb[reach] = np.stack([(40 + 120 * kr).astype(np.uint8), (110 + 120 * kr).astype(np.uint8),
                           (60 + 60 * kr).astype(np.uint8)], -1)
    rgb[under] = np.stack([(shade[under] * 0.6).astype(np.uint8), (shade[under] * 0.85).astype(np.uint8),
                           (shade[under] * 0.6).astype(np.uint8)], -1)
    rgb[~np.isfinite(t)] = (40, 20, 50)        # no floor
    img.paste(Image.fromarray(rgb, 'RGB'), (pad, pad))
    d = ImageDraw.Draw(img)

    def P(x, z):
        return pad + (x - x0) * scale, pad + (z1 - z) * scale

    def cross(x, z, c, s=5, w=2):
        px, pz = P(x, z)
        d.line([px - s, pz - s, px + s, pz + s], fill=c, width=w)
        d.line([px - s, pz + s, px + s, pz - s], fill=c, width=w)

    def dot(x, z, c, s=3):
        px, pz = P(x, z)
        d.ellipse([px - s, pz - s, px + s, pz + s], fill=c)

    def ring(x, z, c, s=6, w=2):
        px, pz = P(x, z)
        d.ellipse([px - s, pz - s, px + s, pz + s], outline=c, width=w)
    conf = confirmed or {}
    for f in finds.get('floorless', []):
        b = f['box']
        d.rectangle([*P(b[0], b[3]), *P(b[2], b[1])], outline=(120, 60, 150))
    for f in finds.get('paths', []):
        for side in ('forward', 'backward'):
            if not f.get(f'{side}_ok', True) and f.get(f'{side}_stop'):
                s = f[f'{side}_stop']
                cross(s[0], s[2], (60, 220, 240), 4, 2)
    for f in finds.get('traps', []):
        if f.get('headless', {}).get('got_out'):
            continue                            # the cart got out: the reach map's miss
        b = f['box']
        d.rectangle([*P(b[0], b[3]), *P(b[2], b[1])], outline=(200, 140, 60), width=2)
    for f in finds.get('falls', []):
        if f.get('confirm', {}).get('confirmed'):
            dot(f['at'][0], f['at'][1], (255, 60, 220), 3)
    for f in finds.get('drops', []):
        if f.get('confirmed'):
            dot(f['at'][0], f['at'][2], (255, 60, 220), 4)
    for f in finds.get('escapes', []):
        ok = f.get('confirm', {}).get('confirmed')
        c = (255, 40, 40) if ok else (150, 90, 90)
        t0 = f['takeoff']['from']
        px, pz = P(t0[0], t0[2])
        qx, qz = P(f['at'][0], f['at'][1])
        if ok:
            d.line([px, pz, qx, qz], fill=c, width=1)
            dot(t0[0], t0[2], c, 2)
        cross(f['at'][0], f['at'][1], c, 5 if ok else 3, 2)
    for s in finds.get('sealed', []):
        b = s['box']
        d.rectangle([*P(b[0], b[5]), *P(b[3], b[2])], outline=(255, 160, 40), width=2)
        for w in s.get('other_ways', []):
            cross(w['from'][0], w['from'][2], (255, 160, 40), 4, 2)
    for c in finds.get('collectibles', []):
        x, y, z = c['at']
        if c['type'] == 'star':
            col = (255, 220, 40) if c['reachable'] else (255, 40, 40)
            px, pz = P(x, z)
            d.regular_polygon((px, pz, 7), 5, fill=col)
            if c.get('glide_take'):
                ring(x, z, (80, 160, 255), 10, 2)
        elif c['type'] == 'red_coin':
            dot(x, z, (230, 50, 40) if c['reachable'] else (255, 255, 255), 3)
        else:
            if not c['reachable']:
                ring(x, z, (255, 255, 255), 4, 1)
    for s in finds.get('shortcuts', []):
        if s.get('bypassed') and s.get('route'):
            pts = [P(q['to'][0], q['to'][2]) for q in s['route'] if q.get('to')]
            if len(pts) > 1:
                d.line(pts, fill=(255, 140, 0), width=1)
    if e.spawn:
        ring(e.spawn[0], e.spawn[2], (255, 255, 255), 6, 2)
    # legend
    y = H - 80
    items = [((90, 200, 90), 'reachable floor'), ((120, 120, 120), 'not reached'), ((255, 40, 40), 'escape (x: where it leaves)'),
             ((255, 60, 220), 'falls through'), ((120, 60, 150), 'no floor (drop check)'), ((255, 160, 40), 'sealed place'),
             ((60, 220, 240), 'path stops'), ((200, 140, 60), 'trap'), ((255, 220, 40), 'star (blue ring: taken gliding)')]
    xx = pad
    for c, label in items:
        d.rectangle([xx, y, xx + 10, y + 10], fill=c)
        d.text((xx + 14, y - 1), label, fill=(230, 230, 230))
        xx += 14 + 6 * len(label) + 16
        if xx > W - 160:
            xx = pad
            y += 16
    d.text((pad, H - 18), f'{e.world.meta["name"]}: x {x0:g}..{x1:g}, z {z0:g}..{z1:g}, north up, {scale:g} px a metre',
           fill=(200, 200, 200))
    img.save(path)
    return path


def _conf(x):
    c = x.get('confirm')
    if not c:
        return ''
    return ' [confirmed headless]' if c.get('confirmed') else ' [not reproduced headless]'


def _route(x):
    r = x.get('route_check')
    if not r:
        return ''
    if r.get('on_foot'):
        return '; route: on foot'
    if r['confirmed']:
        return f'; route: all {r["legs"]} flights reproduced'
    bits = [f'{r["reproduced"]} of {r["legs"]} route flights reproduced']
    if r.get('first_failing'):
        bits.append(f'first off: {" > ".join(r["first_failing"]["move"])} from {r["first_failing"]["from"]}')
    if r.get('not_flown'):
        bits.append(f'{len(r["not_flown"])} not flown')
    return '; route: ' + ', '.join(bits)


def _headless_route(h):
    if h.get('confirmed'):
        moves = [q['move'] for q in h.get('route', []) if q['move'] != 'walk']
        return (f'a route the cart repeats flight by flight, {h["cost_s"]} s ({" > ".join(moves) or "walking"}), '
                f'found in {h["rounds"]} round{"s" if h["rounds"] > 1 else ""}')
    if h.get('no_route'):
        return f'no route left after {h["rounds"]} rounds (each leg the cart did not repeat taken out)'
    if h.get('gave_up'):
        return f'no route the cart repeats in {h["rounds"]} rounds'
    return 'a route with legs the cart cannot fly here: ' + _route({'route_check': h}).lstrip('; ')


def summary_text(rep):
    """The short text summary."""
    out = []
    w = rep['world']
    out.append(f'{w["name"]}: the explorer at {rep.get("commit", "?")} ({rep["seconds"]:.0f} s: reach map '
               f'{rep["timing"].get("reach", 0):.0f} s, confirmer {rep["timing"].get("confirm", 0):.0f} s)')
    g = rep['graph']
    out.append(f'  reach: {g["reachable_floor_entries"]:,} of {g["floor_entries"]:,} floor entries reachable from the '
               f'spawn; {g["flights"]:,} flights')
    f = rep['finds']
    esc = f.get('escapes', [])
    nconf = sum(1 for x in esc if x.get('confirm', {}).get('confirmed'))
    out.append(f'  escapes from the frame: {len(esc)} places, {nconf} confirmed headless')
    for st in f.get('escape_stretches', []):
        out.append(f'    {st["side"]} side, {st["axis"]} {st["from"]:.0f}..{st["to"]:.0f}: {len(st["escapes"])} escapes '
                   f'({", ".join(st["moves"])})')
    out.append('  the escapes, cheapest first:')
    for x in esc[:24]:
        t = x['takeoff']
        out.append(f'    {x["side"]:5s} at ({x["at"][0]:.0f}, {x["at"][1]:.0f}), {x["cost_s"]:.0f} s from the spawn: '
                   f'{" > ".join(t["chain"])} from ({t["from"][0]:.1f}, {t["from"][1]:.1f}, {t["from"][2]:.1f}) '
                   f'heading {t["heading_deg"]:.0f}{_conf(x)}{_route(x)}')
    drops = f.get('drops', [])
    if drops:
        hit = [x for x in drops if x.get('confirmed')]
        out.append(f'  drop check: {len(hit)} of {len(drops)} headless drops over floorless spots fell through the world, '
                   f'in {len(f.get("drop_clusters", []))} places')
        for x in f.get('drop_clusters', [])[:16]:
            n = x['nearest_reachable_floor']
            out.append(f'    ({x["at"][0]:.1f}, {x["at"][1]:.1f}): {x["drops"]} drops; nearest reachable floor '
                       f'({n[0]:.1f}, {n[1]:.1f}, {n[2]:.1f}), {x["nearest_m"]} m')
    falls = f.get('falls', [])
    if falls:
        nconf = sum(1 for x in falls if x.get('confirm', {}).get('confirmed'))
        out.append(f'  flights through the world (reach map): {len(falls)} spots, {nconf} of the first '
                   f'{sum(1 for x in falls if x.get("confirm"))} confirmed headless')
    for s in f.get('sealed', []):
        out.append(f'  sealed: {s["name"]}: ways in (reach map): {", ".join(w["move"] for w in s["ways_in"]) or "none"}')
        h = s.get('headless_other_way')
        if h:
            out.append('    with its intended ways in taken out: ' + _headless_route(h))
        for kind, h in s.get('headless_ways', {}).items():
            out.append(f'    in by {kind} alone: ' + _headless_route(h))
        for rid, r in s.get('rail_drops', {}).items():
            if r['in']:
                out.append(f'    a body dropped onto {rid} grinds into it: {r["in"]} of {r["tried"]} drops (a metre apart '
                           f'along it, at {", ".join(f"{v:g}" for v in r["along_m"][:8])} m)')
            else:
                out.append(f'    drops onto {rid}: none of {r["tried"]} get in')
        for w in s['other_ways'][:8]:
            out.append(f'    not intended: {w["move"]} from ({w["from"][0]:.1f}, {w["from"][1]:.1f}, {w["from"][2]:.1f}), '
                       f'{w["cost_s"]} s from the spawn{_conf(w)}')
    for c in [c for c in f.get('collectibles', []) if c['type'] == 'star']:
        hows = sorted({w['how'].split(' (')[0] for w in c['ways']})
        out.append(f'  {c["id"]}: ' + ('reachable' if c['reachable'] else 'NOT REACHABLE') +
                   (f', taken by {", ".join(hows[:12])}' if hows else '') +
                   (' - TAKEN IN MID-AIR BY A GLIDE' + _conf({'confirm': c.get('glide_confirm')}) if c.get('glide_take') else ''))
    un = [c for c in f.get('collectibles', []) if not c['reachable']]
    out.append(f'  collectibles not reachable: {len(un)}' + (': ' + ', '.join(c['id'] for c in un[:20]) if un else ''))
    for s in f.get('shortcuts', []):
        if 'error' in s:
            out.append(f'  shortcut {s["name"]}: {s["error"]}')
            continue
        h = s.get('headless_route')
        line = (f'  shortcut {s["name"]}: shut, its far side in {s["shut_cost_s"]} s by the reach map, '
                f'{s["route_strays_m"]} m off the line between its ends')
        if h:
            line += '; headless: ' + _headless_route(h)
            if h.get('confirmed'):
                line += (f', {h.get("strays_m")} m off the line: ' +
                         ('BYPASSED' if s.get('bypassed_headless') else 'the long way'))
        else:
            line += ': ' + ('bypassed (reach map only)' if s['bypassed'] else 'the long way')
        out.append(line)
    paths = f.get('paths', [])
    bad = [p for p in paths if not (p['forward_ok'] and p['backward_ok'])]
    out.append(f'  paths that do not walk end to end: {len(bad)} of {len(paths)}')
    for p in bad:
        why = []
        for side in ('forward', 'backward'):
            if not p[f'{side}_ok']:
                r = p.get(f'{side}_why', {})
                at = r.get('at') or p.get(f'{side}_stop')
                why.append(f'{side} stops at {p[f"{side}_to_m"]} m, ({at[0]:.1f}, {at[1]:.1f}, {at[2]:.1f}): {r.get("why")}'
                           + (f' {r.get("rise")} m' if r.get('rise') else '')
                           + (f' {r.get("degrees")} deg' if r.get('degrees') else '')
                           + (f' ({r.get("what")})' if r.get('what') else ''))
        out.append(f'    {p["path"]} ({p["length_m"]} m): ' + '; '.join(why))
    tr = f.get('traps', [])
    out.append(f'  traps (reachable, no way back without a respawn, reach map only): {len(tr)}')
    for t in tr[:12]:
        h = t.get('headless')
        out.append(f'    {t["area_m2"]} m2 at ({t["at"][0]:.1f}, {t["at"][1]:.1f}, {t["at"][2]:.1f})' +
                   ('' if not h else (f': headless, {h["got_out"]} of {h["tried"]} moves got out ({", ".join(h["ways_out"][:3])})'
                                      if h['got_out'] else f': headless, none of {h["tried"]} moves got out')))
    for gd in f.get('glides', []):
        out.append(f'  glide {gd["name"]}: lands from {gd["ok"]} of {gd["tried"]} take-offs; window {gd["window_x"]} m '
                   f'across x ({gd["range_x"]}), {gd["window_z"]} m across z ({gd["range_z"]}); aim errors '
                   + ', '.join(f'{k} deg {"ok" if v else "FAILS"}' for k, v in gd['aim_ok'].items()))
    return '\n'.join(out)


def _public(o):
    """The report without the explorer's own keys (those starting with an underscore)."""
    if isinstance(o, dict):
        return {k: _public(v) for k, v in o.items() if not (isinstance(k, str) and k.startswith('_'))}
    if isinstance(o, list):
        return [_public(v) for v in o]
    return o


def write(rep, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rep = _public(rep)
    (out / 'report.json').write_text(json.dumps(rep, indent=1, default=_default) + '\n')
    text = summary_text(rep)
    (out / 'summary.txt').write_text(text + '\n')
    return text


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, set):
        return sorted(o)
    return str(o)
