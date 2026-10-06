"""Writes the dead cedar of shortcut C (shrine town spec 3.14 and 4.5) beside this script
(python3 make_forest_dead_cedar.py):

- forest_dead_cedar: standing, 35 m, long dead: silver-grey, its top snapped off, a few broken
  limbs, a mossy root plate on its back (+Z) side that is the pound target;
- forest_dead_cedar_fallen: the same tree pounded down (layer cedar_c_down): a jagged 1.8 m stump
  and the log, 33.4 m long, falling 14.25 m along -Z (25.3 degrees, walkable) from the rim to the
  shelf above the falls pool;
- their collision companions, forest_dead_cedar_col and forest_dead_cedar_fallen_col.

Both share one origin, the centre of the trunk at the ground, and one yaw: the world turns -Z to
point across the gorge (from (256, 306) to (226, 318)), so the log falls where the tree stood. The
log's butt rests on the rim 1.1 m in front of the stump; its tip's underside is 14 m below the
origin, 30.6 m out (z = -31.7). Its walking surface (collision) is 1.2 m wide at the butt and 1.0
at the tip.
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent / 'shrine' / 'assets' / 'art'))
import make_foliage as mf  # noqa: E402  (Part, tube, ring helpers)

LIGHT = {'mode': 'vertical', 'ambient': 0.5}
POLICY = {'required': True, 'depth': True, 'perspective': True}
MATS = {'bark': {'color': '#8a8278', 'texture': {'image': 'art/dead_bark.png', 'projection': 'cylindrical',
                                                 'scale': [1.6, 4.8]}},
        'limb': {'color': '#9a948a', 'palette': True},
        'heart': {'color': '#b08a5e', 'palette': True},
        'root': {'color': '#5a4a3e', 'palette': True},
        'mossy': {'color': '#6f8a3c', 'palette': True}}

SIDES = 6
FLARE = [1.0, 0.78, 0.95, 0.8, 1.0, 0.82]
HEIGHT = 35.2                 # the snapped top
STUMP = 1.8                   # where it breaks
LOG_LEN = HEIGHT - STUMP      # 33.4
BUTT = [0.0, 0.66, -1.1]      # the log's butt centre, resting on (a little into) the rim
DROP = 14.0                   # the shelf's height below the rim
TIP_R = 0.5


def log_r(t):
    """The trunk's radius t metres above the break."""
    return 0.78 - (0.78 - TIP_R) * t / LOG_LEN


THETA = math.asin((BUTT[1] - (-DROP + TIP_R)) / LOG_LEN)      # the log's slope


def rings_mesh(part, stations, mat, sides=SIDES, phase=0.0, radii=None, jag=None):
    """An open prism up the Y axis through [(y, r), ...] (radii: per-ring lobes). jag: {ring index:
    (rng, depth, sign)} breaks that ring: each point moved 0 to depth along sign (a broken end)."""
    rings = []
    for k, (y, r) in enumerate(stations):
        lob = radii[k] if radii and radii[k] else [1.0] * sides
        dy = [0.0] * sides
        if jag and k in jag:
            rng, depth, sign = jag[k]
            dy = [sign * rng.uniform(0, depth) for _ in range(sides)]
        rings.append([[r * lob[i] * math.cos(phase + 2 * math.pi * i / sides), y + dy[i],
                       r * lob[i] * math.sin(phase + 2 * math.pi * i / sides)] for i in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            mid = mf.mul(mf.add(a[i], a[j]), 0.5)
            out = [mid[0], 0, mid[2]]
            part.poly([a[i], a[j], b[j]], mat, out)
            part.poly([a[i], b[j], b[i]], mat, out)
    return rings


def jagged_cap(part, rim, mat, up=True, depth=0.3, spikes=()):
    """A broken end over a ring broken by rings_mesh's jag: fanned to a centre point a little
    inside the break; spikes: (index, height) splinters standing on the rim between two points."""
    s = 1 if up else -1
    y0 = min(p[1] * s for p in rim) * s
    centre = [0, y0 + s * depth * 0.35, 0]
    n = len(rim)
    for i in range(n):
        j = (i + 1) % n
        part.poly([rim[i], rim[j], centre], mat, [0, s, 0])
    for i, h in spikes:
        a, b = rim[i], rim[(i + 1) % n]
        a = [a[0] * 0.92, a[1] + s * 0.02, a[2] * 0.92]
        b = [b[0] * 0.92, b[1] + s * 0.02, b[2] * 0.92]
        mid = mf.mul(mf.add(a, b), 0.5)
        tipp = [mid[0] * 0.75, max(a[1] * s, b[1] * s) * s + s * h, mid[2] * 0.75]
        inner = [mid[0] * 0.5, mid[1], mid[2] * 0.5]
        cen = mf.mul(mf.add(mf.add(a, b), mf.add(tipp, inner)), 0.25)
        for tri in ([a, b, tipp], [b, inner, tipp], [inner, a, tipp]):
            fc = mf.mul(mf.add(mf.add(tri[0], tri[1]), tri[2]), 1 / 3)
            part.poly(tri, mat, mf.sub(fc, cen))


def limb(part, start, d, length, r, mat, phase=0.0):
    end = mf.add(start, mf.mul(mf.unit(d), length))
    mf.tube(part, [(start, r), (end, 0.0)], 3, mat, phase=phase, tip=True)


def root_plate(part, mat_side, mat_top):
    """The mossy root plate on the back, the pound target: a low six-sided slab, top at 0.45."""
    c = [0.15, 0, 1.3]
    lob = [1.0, 0.85, 0.95, 1.05, 0.8, 0.9]
    bot = [[c[0] + 1.15 * lob[i] * math.cos(2 * math.pi * i / 6 + 0.3), -0.2,
            c[2] + 0.85 * lob[i] * math.sin(2 * math.pi * i / 6 + 0.3)] for i in range(6)]
    top = [[c[0] + 0.85 * lob[i] * math.cos(2 * math.pi * i / 6 + 0.3), 0.45,
            c[2] + 0.62 * lob[i] * math.sin(2 * math.pi * i / 6 + 0.3)] for i in range(6)]
    for i in range(6):
        j = (i + 1) % 6
        out = [bot[i][0] + bot[j][0] - 2 * c[0], 0, bot[i][2] + bot[j][2] - 2 * c[2]]
        part.poly([bot[i], bot[j], top[j]], mat_side, out)
        part.poly([bot[i], top[j], top[i]], mat_side, out)
    for i in range(1, 5):
        part.poly([top[0], top[i], top[i + 1]], mat_top, [0, 1, 0])


def recipe(name, budget, nodes, levels):
    r = {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'triangles': budget},
         'materials': MATS, 'lighting': LIGHT, 'verification': POLICY, 'nodes': nodes}
    if levels:
        r['lod'] = {'levels': [{'distance': d, 'nodes': ns} for d, ns in levels]}
    return r


# ---------------------------------------------------------------- standing

def standing():
    rng = random.Random(311)
    trunk = mf.Part('trunk')
    rings = rings_mesh(trunk, [(-0.3, 1.15), (STUMP, 0.8), (12.0, 0.7), (24.0, 0.6), (HEIGHT - 0.5, TIP_R)], 'bark',
                       radii=[FLARE, None, None, None, None], jag={4: (rng, 0.9, 1)})
    top = mf.Part('top')
    jagged_cap(top, rings[-1], 'heart', depth=0.9, spikes=[(1, 2.2), (4, 1.2)])
    limbs = mf.Part('limbs')
    for k, (y, a, L, up) in enumerate([(13.5, 0.4, 1.4, -0.3), (17.0, 2.5, 3.2, 0.25), (20.5, 4.4, 1.1, -0.2),
                                       (24.5, 1.4, 2.6, 0.35), (28.0, 3.6, 1.6, 0.1), (31.0, 5.6, 2.2, 0.4)]):
        r = 0.6 - 0.1 * (y - 12) / 12
        start = [math.cos(a) * r * 0.8, y, math.sin(a) * r * 0.8]
        limb(limbs, start, [math.cos(a), up, math.sin(a)], L, 0.13 if L > 2 else 0.1, 'limb', phase=k)
    plate = mf.Part('root_plate')
    root_plate(plate, 'root', 'mossy')
    l1 = mf.Part('trunk')
    r1 = rings_mesh(l1, [(-0.3, 1.0), (STUMP, 0.8), (HEIGHT, TIP_R)], 'limb', sides=4, phase=0.4)
    l1.poly(r1[-1], 'heart', [0, 1, 0])
    limb(l1, [0.6, 17.0, 0.2], [1, 0.25, 0.4], 3.2, 0.13, 'limb')
    limb(l1, [-0.3, 24.5, 0.5], [-0.3, 0.35, 1], 2.6, 0.13, 'limb')
    l2 = mf.Part('trunk')
    rings_mesh(l2, [(0.0, 0.85), (HEIGHT, TIP_R)], 'limb', sides=4, phase=0.4)
    nodes = [trunk.node(), top.node(), limbs.node(), plate.node()]
    return recipe('forest_dead_cedar', 120, nodes, [(45, [l1.node()]), (110, [l2.node()])])


def standing_col():
    p = mf.Part('trunk')
    rings = rings_mesh(p, [(-0.3, 1.0), (STUMP, 0.8), (HEIGHT - 0.4, TIP_R)], 'solid')
    p.poly(rings[-1], 'solid', [0, 1, 0])
    plate = mf.Part('root_plate')
    root_plate(plate, 'solid', 'solid')
    return {'format': 'mei-asset', 'version': 1, 'name': 'forest_dead_cedar_col',
            'materials': {'solid': {'color': '#ffffff', 'palette': True}}, 'lighting': LIGHT,
            'verification': POLICY, 'nodes': [p.node(), plate.node()]}


# ---------------------------------------------------------------- fallen

LOG_ROT = [round(-(90 + math.degrees(THETA)), 4), 0, 0]   # turns the log's +Y down along -Z


def log_axis(t):
    """The point t metres along the log's axis from the butt, in the asset's coordinates."""
    return [BUTT[0], BUTT[1] - t * math.sin(THETA), BUTT[2] - t * math.cos(THETA)]


def fallen():
    rng = random.Random(312)
    stump = mf.Part('stump')
    rings = rings_mesh(stump, [(-0.3, 1.15), (1.0, 0.84), (STUMP - 0.3, 0.8)], 'bark',
                       radii=[FLARE, None, None], jag={2: (rng, 0.6, 1)})
    jagged_cap(stump, rings[-1], 'heart', depth=0.6, spikes=[(0, 0.9), (3, 0.5)])
    # the log, built up its own Y axis (so the bark's cylindrical projection runs along it) and
    # turned into place by its transform
    log = mf.Part('log')
    lr = rings_mesh(log, [(0.3, log_r(0)), (11.0, log_r(11)), (22.0, log_r(22)), (LOG_LEN - 0.3, log_r(LOG_LEN))],
                    'bark', phase=0.5, jag={0: (rng, 0.6, -1), 3: (rng, 0.5, 1)})
    jagged_cap(log, lr[0], 'heart', up=False, depth=0.6, spikes=[(2, 0.8)])
    jagged_cap(log, lr[-1], 'heart', depth=0.5)
    # broken limbs along its sides and underside (log-local +Z is the log's top): none on top
    for k, (t, sx, L) in enumerate([(9.0, 1, 1.3), (14.5, -1, 2.0), (21.0, 1, 1.6), (27.5, -1, 1.1)]):
        r = log_r(t)
        start = [sx * r * 0.8, t, -0.1]
        limb(log, start, [sx, 0.15, -0.55], L, 0.12, 'limb', phase=k)
    plate = mf.Part('root_plate')
    root_plate(plate, 'root', 'mossy')
    lnode = log.node()
    lnode['transform'] = {'rotate': LOG_ROT, 'translate': BUTT}
    # level 1: a four-sided stump and log
    l1s = mf.Part('stump')
    s1 = rings_mesh(l1s, [(-0.3, 1.0), (STUMP, 0.8)], 'limb', sides=4, phase=0.4)
    l1s.poly(s1[-1], 'heart', [0, 1, 0])
    l1l = mf.Part('log')
    g1 = rings_mesh(l1l, [(0.0, log_r(0)), (LOG_LEN, log_r(LOG_LEN))], 'limb', sides=4, phase=0.0)
    l1l.poly(g1[0], 'heart', [0, -1, 0])
    l1l.poly(g1[-1], 'heart', [0, 1, 0])
    l1n = l1l.node()
    l1n['transform'] = {'rotate': LOG_ROT, 'translate': BUTT}
    l2l = mf.Part('log')
    rings_mesh(l2l, [(0.0, log_r(0)), (LOG_LEN, log_r(LOG_LEN))], 'limb', sides=3, phase=math.pi / 2)
    l2n = l2l.node()
    l2n['transform'] = {'rotate': LOG_ROT, 'translate': BUTT}
    nodes = [stump.node(), lnode, plate.node()]
    return recipe('forest_dead_cedar_fallen', 120, nodes, [(45, [l1s.node(), l1n]), (110, [l2n])])


BUTT_TOP = 1.26              # the log's walking top at its butt (0.66 + 0.85 r cos theta)


def fallen_col():
    """The stump's walls and flat top, the root plate, and the log's walking slab: four sides
    in four lengths of 8.35 m (no floor triangle longer than 8:1), its top 0.85 of the log's radius
    above the axis, 1.2 m wide at the butt and 1.0 at the tip. The stump's top is the slab's top at the
    butt (1.26), and a floor joins the two over the 0.6 m between them (alpha fix, shrine town
    DESIGN.md 12.9: the top was 1.6 and nothing joined them, so a body dropped through there to the
    gorge, and the log was walked onto only by a hop from the stump)."""
    p = mf.Part('stump')
    rings = rings_mesh(p, [(-0.3, 1.0), (BUTT_TOP, 0.8)], 'solid')
    p.poly(rings[-1], 'solid', [0, 1, 0])
    p.poly([[-0.65, BUTT_TOP - 0.02, -0.5], [0.65, BUTT_TOP - 0.02, -0.5], [0.65, BUTT_TOP - 0.02, -1.45],
            [-0.65, BUTT_TOP - 0.02, -1.45]],
           'solid', [0, 1, 0])
    plate = mf.Part('root_plate')
    root_plate(plate, 'solid', 'solid')
    slab = mf.Part('log')
    n_seg = 4
    up = [0, math.cos(THETA), -math.sin(THETA)]          # the log's top, square to its axis
    secs = []
    for k in range(n_seg + 1):
        t = LOG_LEN * k / n_seg
        c = log_axis(t)
        w = 0.6 - 0.1 * t / LOG_LEN
        top = mf.add(c, mf.mul(up, 0.85 * log_r(t)))
        bot = mf.add(c, mf.mul(up, -0.4 * log_r(t)))
        secs.append([mf.add(top, [-w, 0, 0]), mf.add(top, [w, 0, 0]), mf.add(bot, [w, 0, 0]), mf.add(bot, [-w, 0, 0])])
    outs = [up, [1, 0, 0], mf.mul(up, -1), [-1, 0, 0]]
    for a, b in zip(secs, secs[1:]):
        for i in range(4):
            j = (i + 1) % 4
            slab.poly([a[i], a[j], b[j]], 'solid', outs[i])
            slab.poly([a[i], b[j], b[i]], 'solid', outs[i])
    axis = [0, -math.sin(THETA), -math.cos(THETA)]
    slab.poly(secs[0], 'solid', mf.mul(axis, -1))
    slab.poly(secs[-1], 'solid', axis)
    return {'format': 'mei-asset', 'version': 1, 'name': 'forest_dead_cedar_fallen_col',
            'materials': {'solid': {'color': '#ffffff', 'palette': True}}, 'lighting': LIGHT,
            'verification': POLICY, 'nodes': [p.node(), plate.node(), slab.node()]}


def main():
    for r in [standing(), standing_col(), fallen(), fallen_col()]:
        (HERE / f"{r['name']}.asset.json").write_text(json.dumps(r, indent=1) + '\n')
        print('wrote', r['name'])
    print(f'log: {LOG_LEN:.1f} m, slope {math.degrees(THETA):.2f} degrees, tip axis at {[round(v, 2) for v in log_axis(LOG_LEN)]}')


if __name__ == '__main__':
    main()
