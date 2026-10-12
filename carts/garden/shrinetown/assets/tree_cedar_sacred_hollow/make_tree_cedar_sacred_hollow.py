"""Writes tree_cedar_sacred_hollow.asset.json and its collision, tree_cedar_sacred_hollow_col, beside
this script (python3 make_tree_cedar_sacred_hollow.py).

The shrine's sacred cedar (carts/garden/shrine/assets/art/make_foliage.py, sacred()) made hollow for
shrine town's star 4 (spec 3.10 and 5): the same crown, leaders, shimenawa and shide, round a trunk
that is now a shell. Its front (-Z, which the world turns to face the rope deck) has:

- the knot hole: 1.4 m wide, its sill 8.5 m above the base and its top 10.7, a 1.65 m tunnel through
  a burl into the shaft;
- the bark lip: the burl's brow, 1.45 m out past the sill's edge, its underside at 10.7-10.95 and
  its top a 48-degree slope (a wall: nothing stands on it);
- two cheeks either side of the hole, 1.3 m out past the sill and down to 7.7 m, so the hole is
  open only to the front: nothing falling beside the burl or flying round the trunk reaches the sill;
- the shaft, 3.7 m across, from the hole down to the root chamber (4.8 m across, 2.2 m tall, its
  floor at 0.08), its ceiling at 12.2;
- the root door: a 1.4 x 2.3 m opening through the root flare into the chamber, below the hole,
  which forest_root_curtain (layer root_d_open off) closes;
- the root bulge on the chamber floor (the pound target that opens the door).

Nothing on the outside between the roots (2.3 m) and the burl's underside (5.2 m at the trunk,
7.3 at its front) is a ledge in the collision: the shimenawa is drawn, not collided.
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHRINE_ART = HERE.parent.parent.parent / 'shrine' / 'assets' / 'art'
sys.path.insert(0, str(SHRINE_ART))
import make_foliage as mf  # noqa: E402  (the shrine forest's helpers: Part, card, tube, cedar_crown)

NAME = 'tree_cedar_sacred_hollow'
SHEETS = {'foliage': {'image': '../../../shrine/assets/art/foliage.png'}}
LIGHT = {'mode': 'vertical', 'ambient': 0.55}
POLICY = {'required': True, 'depth': True, 'perspective': True}

HW = 0.7            # half the width of the knot hole and the root door: the front face of every ring
SILL, HOLE_TOP = 8.5, 10.7
DOOR_TOP = 2.3
FLOOR = 0.08        # the chamber's floor, above the terrain at 0
CEIL = 12.2         # the shaft's ceiling
SHAFT_R, CHAMBER_R = 1.85, 2.4
INNER_Z = 0.06      # the burl's pieces reach this far into the shaft past its front face


# ---------------------------------------------------------------- rings with a flat front

def ring(y, r, n, front=None, lobes=None, hw=HW):
    """n points round the Y axis at height y: points 0 and 1 are the front face's corners at
    x = -hw and +hw (depth front, or on the circle), the others spread evenly round the back."""
    d = front if front is not None else math.sqrt(r * r - hw * hw)
    a0 = math.atan2(hw, d)
    span = 2 * math.pi - 2 * a0
    pts = [[-hw, y, -d], [hw, y, -d]]
    for k in range(1, n - 1):
        a = a0 + span * k / (n - 1)
        rr = r * (lobes[k + 1] if lobes else 1.0)
        pts.append([rr * math.sin(a), y, -rr * math.cos(a)])
    return pts


def band(part, lo, hi, mat, inward=False, skip=()):
    """The quads between two rings of the same count, facing out (or in, for the hollow), except
    the sides in skip (side 0 is the front face)."""
    n = len(lo)
    for i in range(n):
        if i in skip:
            continue
        j = (i + 1) % n
        mid = mf.mul(mf.add(lo[i], lo[j]), 0.5)
        out = [mid[0], 0, mid[2]]
        if inward:
            out = mf.mul(out, -1)
        part.poly([lo[i], lo[j], hi[j]], mat, out)
        part.poly([lo[i], hi[j], hi[i]], mat, out)


def cap(part, rng_pts, mat, up):
    """A flat cap over a ring, facing up (or down)."""
    centre = [sum(p[0] for p in rng_pts) / len(rng_pts), rng_pts[0][1], sum(p[2] for p in rng_pts) / len(rng_pts)]
    n = len(rng_pts)
    for i in range(n):
        j = (i + 1) % n
        pts = [rng_pts[i], rng_pts[j], centre]
        part.poly(pts, mat, [0, 1 if up else -1, 0])


def prism_x(part, profile, inner, outer, mat, edge_mats=None, inner_mat=None, fan=0):
    """A closed prism across x: profile [(z, y), ...] (the side view) between two caps. inner and
    outer give each cap's x as (x at the profile's back, x at its front, z of the back, z of the
    front): a cap is a plane, leaning in towards the front so the burl rounds off. The caps are
    fanned from profile point fan (a reflex corner, where there is one); edge_mats names the
    material of the wall over edge k (from point k to k + 1)."""
    edge_mats = edge_mats or {}

    def x_at(spec, z):
        xb, xf, zb, zf = spec
        return xb + (xf - xb) * (z - zb) / (zf - zb)
    n = len(profile)
    area = sum(profile[k][0] * profile[(k + 1) % n][1] - profile[(k + 1) % n][0] * profile[k][1] for k in range(n))
    sx = 1 if outer[0] > inner[0] else -1
    a = [[x_at(inner, z), y, z] for z, y in profile]
    b = [[x_at(outer, z), y, z] for z, y in profile]
    for k in range(1, n - 1):
        i, j = (fan + k) % n, (fan + k + 1) % n
        part.poly([a[fan], a[i], a[j]], inner_mat or mat, [-sx, 0, 0])
        part.poly([b[fan], b[i], b[j]], mat, [sx, 0, 0])
    for k in range(n):
        j = (k + 1) % n
        dz, dy = profile[j][0] - profile[k][0], profile[j][1] - profile[k][1]
        out = [0, -dz, dy] if area > 0 else [0, dz, -dy]
        m = edge_mats.get(k, mat)
        part.poly([a[k], a[j], b[j]], m, out)
        part.poly([a[k], b[j], b[k]], m, out)


# ---------------------------------------------------------------- the burl round the knot hole

ZS = -math.sqrt(SHAFT_R ** 2 - HW ** 2) + INNER_Z     # the burl's back, just inside the shaft
SILL_EDGE, CHEEK_FRONT, LIP_FRONT = -3.3, -4.6, -4.75

CHIN = [(ZS, 5.2), (-2.6, 5.2), (SILL_EDGE, 7.3), (SILL_EDGE, SILL), (ZS, SILL)]
ZC = ZS + 0.05      # the cheeks' backs, 5 cm past the chin's and the brow's (no shared plane)
CHEEK = [(ZC, 8.3), (-3.1, 8.3), (-3.1, 7.2), (CHEEK_FRONT, 7.7), (CHEEK_FRONT, 11.3), (ZC, 11.3)]
BROW = [(ZS, HOLE_TOP), (SILL_EDGE, HOLE_TOP), (LIP_FRONT, 10.95), (LIP_FRONT, 11.55), (-2.05, 14.6), (ZS, 14.6)]
CHIN_W, CHEEK_X, BROW_W = 1.35, 1.55, 1.75


def burl_nodes(mat, back='hollow', cut='cut'):
    """The chin under the sill, the two cheeks and the brow (the bark lip): bark outside, the
    hole's sill, sides and ceiling in cut wood, their backs (inside the shaft) in the hollow's
    colour. Collision passes the same material for all."""
    chin, cheeks, brow = mf.Part('chin'), mf.Part('cheeks'), mf.Part('brow')
    prism_x(chin, CHIN, (-CHIN_W, -1.1, ZS, SILL_EDGE), (CHIN_W, 1.1, ZS, SILL_EDGE), mat,
            {3: cut, 4: back}, inner_mat=mat)
    for sx in (-1, 1):
        prism_x(cheeks, CHEEK, (sx * HW, sx * HW, ZC, CHEEK_FRONT), (sx * CHEEK_X, sx * 1.3, ZC, CHEEK_FRONT), mat,
                {5: back}, inner_mat=cut, fan=1)
    prism_x(brow, BROW, (-BROW_W, -1.45, ZS, LIP_FRONT), (BROW_W, 1.45, ZS, LIP_FRONT), mat,
            {0: cut, 5: back}, inner_mat=mat)
    return [chin.node(), cheeks.node(), brow.node()]


# ---------------------------------------------------------------- the shell

N_OUT, N_IN = 12, 10
LOBES0 = [1.0, 1.0, 0.66, 0.9, 0.62, 1.05, 0.7, 0.95, 0.6, 1.0, 0.64, 0.88]
LOBES1 = [1.0, 1.0, 0.95, 0.98, 0.93, 1.0, 0.94, 0.98, 0.93, 1.0, 0.95, 0.97]


def outer_rings():
    return {'root': ring(-0.2, 3.7, N_OUT, front=3.4, lobes=LOBES0),
            'door': ring(DOOR_TOP, 3.0, N_OUT, front=2.95, lobes=LOBES1),
            'burl': ring(5.6, 2.75, N_OUT),
            'fork': ring(15.0, 2.05, N_OUT)}


def inner_rings():
    hs = [('floor', FLOOR, CHAMBER_R), ('door', DOOR_TOP, CHAMBER_R), ('neck', 3.2, SHAFT_R),
          ('sill', SILL, SHAFT_R), ('top', HOLE_TOP, SHAFT_R), ('ceil', CEIL, SHAFT_R)]
    return {k: ring(y, r, N_IN) for k, y, r in hs}


def shell(outer_mat, roots_mat, hollow_mat, floor_mat, cut_mat):
    """The trunk's outside, the hollow inside it and the root door between them (meshes)."""
    o, i = outer_rings(), inner_rings()
    roots = mf.Part('roots')
    band(roots, o['root'], o['door'], roots_mat, skip={0})
    trunk = mf.Part('trunk')
    band(trunk, o['door'], o['burl'], outer_mat)
    band(trunk, o['burl'], o['fork'], outer_mat, skip={0})
    hollow = mf.Part('hollow')
    band(hollow, i['floor'], i['door'], hollow_mat, inward=True, skip={0})
    band(hollow, i['door'], i['neck'], hollow_mat, inward=True)
    band(hollow, i['neck'], i['sill'], hollow_mat, inward=True)
    band(hollow, i['sill'], i['top'], hollow_mat, inward=True, skip={0})
    band(hollow, i['top'], i['ceil'], hollow_mat, inward=True)
    cap(hollow, i['ceil'], hollow_mat, up=False)
    cap(hollow, i['floor'], floor_mat, up=True)
    # the root door: jambs, lintel and threshold between the outer and inner front faces
    door = mf.Part('door')
    ob, ot, ib, it = o['root'], o['door'], i['floor'], i['door']
    door.poly([ob[0], ot[0], it[0], ib[0]], cut_mat, [1, 0, 0])
    door.poly([ob[1], ot[1], it[1], ib[1]], cut_mat, [-1, 0, 0])
    door.poly([ot[0], ot[1], it[1], it[0]], cut_mat, [0, -1, 0])
    door.poly([ob[0], ob[1], ib[1], ib[0]], floor_mat, [0, 1, 0])
    return [roots, trunk, hollow, door]


def bulge(mat):
    """The root bulge on the chamber floor, at the back: a low lumpy mound (a lathe)."""
    return {'id': 'root_bulge', 'op': 'lathe', 'profile': [[0.75, 0], [0.55, 0.25], [0.0, 0.42]],
            'segments': 6, 'caps': False, 'material': mat,
            'transform': {'scale': [1.0, 1.0, 0.75], 'rotate': [0, 15, 0], 'translate': [0.25, FLOOR - 0.02, 1.15]}}


# ---------------------------------------------------------------- the rest of the sacred cedar

def leaders_part():
    """Three leaders from the fork at 15 m and six limbs into the crown, as the shrine's cedar."""
    leaders = mf.Part('leaders')
    tops = []
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        base = [math.cos(a) * 0.9, 14.0, math.sin(a) * 0.9]
        top = [math.cos(a) * 2.6, 41.0 - k * 2.5, math.sin(a) * 2.6]
        tops.append(top)
        mf.tube(leaders, [(base, 1.15), (mf.mul(mf.add(base, top), 0.5), 0.75), (top, 0.12)], 5, 'bark',
                phase=a, quads=False)
    for k in range(6):
        t = tops[k % 3]
        a = k * 2.1 + 0.2
        y = 21.0 + k * 2.6
        start = [t[0] * (y - 14) / 27, y, t[2] * (y - 14) / 27]
        L = 6.0 - k * 0.5
        end = mf.add(start, [math.cos(a) * L, L * 0.45, math.sin(a) * L])
        mf.tube(leaders, [(start, 0.35), (end, 0.08)], 3, 'limb', phase=k)
    return leaders


def shimenawa(y0=4.0, r_in=2.62, r_out=3.0, n=12, half=0.24):
    """The rope ring at 4 m, its inner edge inside the trunk (two faces a segment), and the shide."""
    rope = mf.Part('shimenawa', uvs=True)
    sag = lambda a: -0.12 * math.cos(a - 0.4) ** 2
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n

        def pt(a, r, dy):
            return [math.cos(a) * r, y0 + dy + sag(a), math.sin(a) * r]
        u0, u1 = i * 2.0, (i + 1) * 2.0
        top0, top1 = pt(a0, r_in, half), pt(a1, r_in, half)
        out0, out1 = pt(a0, r_out, 0), pt(a1, r_out, 0)
        bot0, bot1 = pt(a0, r_in, -half), pt(a1, r_in, -half)
        for (p0, p1, q1, q0), (va, vb) in [((out0, out1, top1, top0), (0.0, 1.0)), ((bot0, bot1, out1, out0), (1.0, 2.0))]:
            pts = [(p0, (u0, vb)), (p1, (u1, vb)), (q1, (u1, va)), (q0, (u0, va))]
            nrm = mf.cross(mf.sub(p1, p0), mf.sub(q0, p0))
            outv = [math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2)]
            if mf.dot(nrm, outv) < 0:
                pts = pts[::-1]
            rope.face([rope.vert(p, t) for p, t in pts], 'rope')
    paper = mf.Part('shide', uvs=True)
    for k in range(8):
        a = k * 2 * math.pi / 8 + 0.25
        r = r_out + 0.04
        c = [math.cos(a) * r, y0 - 0.62 - 0.12 * math.cos(a - 0.4) ** 2, math.sin(a) * r]
        mf.card(paper, c, [math.cos(a), 0, math.sin(a)], 0.4, 0.8, 'paper')
    return rope, paper


def crown_part(seed, tufts, ident='crown'):
    rng = random.Random(seed)
    crown = mf.Part(ident, uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        mf.card(crown, [0, 17.0, 0], [math.cos(a), 0, math.sin(a)], 10.0, 28.5, 'far', uv=(0, 0, 1, 0.7), lift=1.0)
    mf.cedar_crown(crown, rng, 17.0, 44.5, 10.5, 7.0, tufts, 'leaves', droop=-0.3, dome=True)
    return crown


# ---------------------------------------------------------------- levels of detail

def level1():
    """From 48 m: an 8-sided trunk, the burl as one block with the hole and the door as dark
    decals, the leaders as three spikes and a thinner crown."""
    wood = mf.Part('trunk')
    r0 = ring(-0.2, 3.4, 8, front=3.15)
    r1 = ring(DOOR_TOP, 2.95, 8)
    r2 = ring(15.0, 2.05, 8)
    band(wood, r0, r1, 'moss')
    band(wood, r1, r2, 'bark')
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        base = [math.cos(a) * 0.9, 14.0, math.sin(a) * 0.9]
        top = [math.cos(a) * 2.6, 41.0 - k * 2.5, math.sin(a) * 2.6]
        mf.tube(wood, [(base, 1.0), (top, 0.0)], 3, 'limb', phase=a, tip=True)
    rng = random.Random(107)
    crown = mf.Part('crown', uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        mf.card(crown, [0, 17.0, 0], [math.cos(a), 0, math.sin(a)], 12.0, 28.5, 'far', uv=(0, 0, 1, 0.7), lift=1.0)
    mf.cedar_crown(crown, rng, 17.5, 43.5, 10.0, 8.6, 30, 'leaves', droop=-0.3, dome=True)
    burl = {'id': 'burl', 'op': 'box', 'size': [3.2, 6.6, 2.0], 'material': 'burl',
            'decals': [{'id': 'hole', 'face': 'back', 'material': 'hollow', 'size': [1.4, 2.2],
                        'at': [0, SILL + 1.1 - 9.0]}],
            'transform': {'translate': [0, 9.0, -2.95]}}
    door = {'id': 'door_dark', 'op': 'box', 'size': [1.4, 2.25, 0.3], 'material': 'hollow', 'open': ['bottom', 'front'],
            'transform': {'translate': [0, 1.125, -3.02]}}
    return [wood.node(), crown.node(), burl, door]


def level2():
    far = mf.Part('far', uvs=True)
    for k in range(3):
        a = 0.2 + k * math.pi / 3
        mf.card(far, [0, 0, 0], [math.cos(a), 0, math.sin(a)], 16.0, 46.0, 'far', lift=1.0, quad=True)
    return [far.node()]


# ---------------------------------------------------------------- recipes

def tris(nodes_parts):
    return sum(p.tris() for p in nodes_parts)


def build():
    mats = {'bark': mf.tile('cedar_bark_tile', '#6a4632', [1.8, 6.4]),
            'burl': {'color': '#6a4632', 'texture': {'sheet': 'foliage', 'cell': 'cedar_bark_tile',
                                                     'projection': 'box', 'scale': [1.8, 3.6]}},
            'moss': mf.tile('moss', '#5f7a34', [1.6, 1.6]),
            'rope': mf.tile('rope', '#c8b478', [0.5, 0.25]),
            'paper': mf.tex('shide', '#ece4d2'),
            'limb': mf.pal('#6a4632'),
            'hollow': mf.pal('#3a2a20'),
            'floor': mf.pal('#6a4a30'),
            'cut': mf.pal('#8a6446'),
            'leaves': mf.tex('cedar', '#2e4a2e'),
            'far': mf.tex('cedar_far', '#2e4a2e')}
    parts = shell('bark', 'moss', 'hollow', 'floor', 'cut')
    leaders = leaders_part()
    rope, paper = shimenawa()
    crown = crown_part(106, 48)
    nodes = [p.node() for p in parts] + burl_nodes('burl') + [bulge('cut'), leaders.node(), rope.node(),
                                                               paper.node(), crown.node()]
    r = {'format': 'mei-asset', 'version': 1, 'name': NAME, 'budget': {'triangles': 600},
         'materials': mats, 'lighting': LIGHT, 'verification': POLICY, 'sheets': SHEETS,
         'nodes': nodes,
         'lod': {'levels': [{'distance': 48, 'nodes': level1()}, {'distance': 180, 'nodes': level2()}]}}
    return r


def build_col():
    """Walls where the trunk stops the player, the burl's pieces as they are drawn (their tops
    are walls or out of reach, the sill is the floor), the hollow's walls, floor and ceiling, the
    root door's jambs and lintel, the root bulge, and a cone over the fork (56 degrees: nothing
    stands on top of the trunk)."""
    o, i = outer_rings(), inner_rings()
    # smooth outside: no lobes, so the roots are a wall, not steps
    o['root'] = ring(-0.2, 3.3, N_OUT, front=3.3)
    o['door'] = ring(DOOR_TOP, 2.95, N_OUT, front=2.95)
    walls = mf.Part('outside')
    band(walls, o['root'], o['door'], 'solid', skip={0})
    band(walls, o['door'], o['burl'], 'solid')
    band(walls, o['burl'], o['fork'], 'solid', skip={0})
    top = [0, 18.0, 0]
    for k in range(N_OUT):
        j = (k + 1) % N_OUT
        a, b = o['fork'][k], o['fork'][j]
        mid = mf.mul(mf.add(a, b), 0.5)
        walls.poly([a, b, top], 'solid', [mid[0], 0.6, mid[2]])
    hollow = mf.Part('hollow')
    band(hollow, i['floor'], i['door'], 'solid', inward=True, skip={0})
    band(hollow, i['door'], i['neck'], 'solid', inward=True)
    band(hollow, i['neck'], i['sill'], 'solid', inward=True)
    band(hollow, i['sill'], i['top'], 'solid', inward=True, skip={0})
    band(hollow, i['top'], i['ceil'], 'solid', inward=True)
    cap(hollow, i['ceil'], 'solid', up=False)
    cap(hollow, i['floor'], 'solid', up=True)
    door = mf.Part('door')
    ob, ot, ib, it = o['root'], o['door'], i['floor'], i['door']
    door.poly([ob[0], ot[0], it[0], ib[0]], 'solid', [1, 0, 0])
    door.poly([ob[1], ot[1], it[1], ib[1]], 'solid', [-1, 0, 0])
    door.poly([ot[0], ot[1], it[1], it[0]], 'solid', [0, -1, 0])
    door.poly([ob[0], ob[1], ib[1], ib[0]], 'solid', [0, 1, 0])
    bul = {'id': 'root_bulge', 'op': 'box', 'size': [1.1, 0.34, 0.8], 'material': 'solid', 'open': ['bottom'],
           'transform': {'rotate': [0, 15, 0], 'translate': [0.25, FLOOR + 0.17 - 0.01, 1.15]}}
    nodes = [walls.node(), hollow.node(), door.node()] + burl_nodes('solid', 'solid', 'solid') + [bul]
    return {'format': 'mei-asset', 'version': 1, 'name': NAME + '_col',
            'materials': {'solid': mf.pal('#ffffff')}, 'lighting': {'mode': 'vertical', 'ambient': 0.5},
            'verification': POLICY, 'nodes': nodes}


def main():
    for name, r in [(NAME, build()), (NAME + '_col', build_col())]:
        (HERE / f'{name}.asset.json').write_text(json.dumps(r, indent=1) + '\n')
        print(f'wrote {name}.asset.json')


if __name__ == '__main__':
    main()
