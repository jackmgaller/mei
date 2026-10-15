#!/usr/bin/env python3
"""Mech Expo 2000: Momentum's angel (MR-02), concept A, fourth look study: jointed wings.

Not packed and not in the roster (it lives outside models/). Round three (make_angel_a3.py,
beside this script) gave the angel a body of its own on Shadow's skeleton; the owner chose its
paint scheme 1, "Gauntlets". This round builds on that body, importing its parts, and changes
three things:

  paint    scheme 1 with each wing's red made broad and solid: the upper wing plate (the
           covert, its arch over the shoulder) is larger and red on both faces, edged in white,
           where round three had a narrow red band on a white plate; it reads as red at true
           game scale. The two flight plates under it stay chrome (both faces, so a spread wing
           seen from behind is not dark), longer and fanned apart; the pauldrons' lower tier
           stays red, and gold stays on the holy parts only (halo, crest and temple wings, the
           core's setting, the knuckles).
  joints   the wings get a joint each, two new joints on the shared skeleton:

             wing_l   parent torso, offset (0.82, 2.72, 0.95): the root high on the back, at
                      the side of the wing pack (a gunmetal hinge drum shows it)
             wing_r   parent torso, offset (-0.82, 2.72, 0.95), the left one mirrored

           Their frame is the torso's (no rest rotation); folded is the rest pose (every
           rotation 0), so every move carried over from Shadow, which keys no wing, shows the
           wings folded. Every existing joint keeps Shadow's offset, so Shadow's keyframes apply
           unchanged. Spread (WING_SPREAD) is x -122, y 50, z -24 on the left wing (the right
           mirrored: y and z negated): the tips swung up, out and back, the outer face turned
           part to the front and part to the side, so the front camera sees a wide V and the
           side camera a fan rising behind the shoulders. Range for the animators: x -130..10,
           y -10..65, z -35..10 (left; right mirrored).
  Judgement  the wings spread wide and up, the right fist raised, the halo raised 0.9 m off
           the helm and made a third larger (in the game that lift belongs to the effect, the
           halo flaring, or to a halo joint: a halo is part of the head mesh).

The Judgement effect itself (a white-gold column of light slamming down on the opponent, the
halo flaring) is not built here; render_angel_a4.py puts a stand-in column on the opponent for
the sheets.

1,844 triangles (round three 1,892; Shadow 1,800; the Hero 1,776): each wing drops round three's
band plate (36) and gains a hinge drum (12).

Writes, beside this script: angel_a4_{idle,attack,judgement,rest,spread}.asset.json (the spread
is the rest pose with the wings spread, for the wing close-ups), cameras_a4.json.
render_angel_a4.py renders them beside Shadow and the Hero and draws the sheets.
Run from anywhere: python3 carts/mechexpo/concepts/angel_a/make_angel_a4.py (standard library
only).
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_angel_a3 as A3  # noqa: E402

H, S, T, group, plate_yz = A3.H, A3.S, A3.T, A3.group, A3.plate_yz

# ---- paint: scheme 1, the covert red and solid --------------------------------------------------

SCHEME = {**A3.SCHEME_1, 'covert': 'red', 'covert_edge': 'white'}

# ---- the wing: its own part, on its own joint ---------------------------------------------------
# In the wing joint's frame (the torso's axes, the origin at the root), the plates as round three
# had them (turned by A3.WING_TURN), the covert larger: it reaches further down over the flight
# plates and wider behind, so the red is a big shape. Outlines (z, y), +z back.

COVERT = [(-0.28, -0.3), (-0.34, 0.75), (-0.02, 1.5), (0.5, 1.92), (1.0, 1.76), (1.36, 1.0),
          (1.52, -0.6), (1.42, -2.2), (1.16, -3.1), (0.5, -1.6)]
WING_ROOT = A3.WING_ROOT
WING_SPREAD = [-122, 50, -24]      # the left wing's; the right's is mirrored (y, z negated)


# The flight plates, longer and broader than round three's and fanned at the root (the lower
# one swung 14 degrees back, the upper 4 forward), so the tips step apart: folded, the wing
# trails a clean double point behind the calves; spread, the two plates open into a fan.
FLIGHT_A = [(0.1, 0.3), (0.85, 0.95), (1.45, 0.4), (1.75, -1.3), (1.7, -3.4), (1.4, -4.5),
            (0.85, -1.8)]
FLIGHT_B = [(0.3, -0.2), (1.15, 0.2), (1.75, -0.9), (2.0, -3.0), (1.9, -5.0), (1.55, -6.0),
            (1.0, -3.0)]
FAN_A, FAN_B = 4, -14


def wing():
    """The left wing, in its joint's frame."""
    plates = [
        plate_yz('covert', COVERT, 0.1, 'covert', 'covert', 'covert_edge', [0.15, 0, 0]),
        group('fan_a', [plate_yz('flight_a', FLIGHT_A, 0.08, 'flight', 'flight', 'flight_edge',
                                 [0.02, 0, 0])], None, [FAN_A, 0, 0]),
        group('fan_b', [plate_yz('flight_b', FLIGHT_B, 0.08, 'flight', 'flight', 'flight_edge',
                                 [-0.1, 0, 0])], None, [FAN_B, 0, 0]),
    ]
    hinge = H.cyl_x('hinge', 0.3, 0.34, 4, 'frame', [0.0, 0, 0])
    return [hinge, group('folded', plates, None, A3.WING_TURN)]


def torso():
    """Round three's torso without its wings (they are parts of their own now)."""
    return [n for n in A3.torso() if not n['id'].startswith('wing_') or n['id'] == 'wing_pack']


def head(lift=0.0, scale=1.0):
    """Round three's helm; `lift` raises the halo (metres) and `scale` grows it."""
    nodes = copy.deepcopy(A3.head())
    helm = nodes[-1]
    ring = next(n for n in helm['children'] if n['id'] == 'halo')
    at = list(A3.HALO_AT)
    at[1] += lift
    ring['transform'] = T(at, A3.HALO_TILT, [scale, scale, scale] if scale != 1.0 else None)
    return nodes


PARTS = {**A3.PARTS, 'torso': torso, 'wing': wing}


def skeleton():
    """Shadow's skeleton (make_shadow.skeleton, its offsets unchanged) and the two wing joints."""
    x, y, z = WING_ROOT
    return S.skeleton() + [('wing_l', 'torso', [x, y, z], None, 'wing', 'l'),
                           ('wing_r', 'torso', [-x, y, z], None, 'wing', 'r')]


def assemble(stance, drop, dz=0.0, parts=PARTS):
    """The rig as nested groups (make_angel_a3.assemble with the wing joints)."""
    sk = skeleton()
    kids = {}
    for jid, parent, *_ in sk:
        kids.setdefault(parent, []).append(jid)

    def node(jid):
        _, parent, offset, rest, part, side = next(e for e in sk if e[0] == jid)
        t = list(offset)
        if parent is None:
            t[1] -= drop
            t[2] += dz
        inner = {'id': jid, 'op': 'group',
                 'children': H.geometry(part, side, parts) + [node(k) for k in kids.get(jid, [])],
                 'transform': T(None, stance.get(jid))}
        if rest:
            return {'id': f'{jid}_mount', 'op': 'group', 'children': [inner],
                    'transform': T([round(c, 4) for c in t], rest)}
        inner['transform'] = T([round(c, 4) for c in t], stance.get(jid))
        return inner
    return [node('pelvis')]


def recipe(name, nodes, budget=1900):
    return A3.recipe(name, nodes, SCHEME, budget)


def spread(st):
    return {**st, 'wing_l': list(WING_SPREAD), 'wing_r': A3.mirror(WING_SPREAD)}


def poses():
    """{name: (stance, drop, dz, parts)}: round three's idle and attack (the wings folded), and
    Judgement with the wings spread and the halo raised; the rest, and the rest spread."""
    p3 = A3.poses()
    judged = {**PARTS, 'head': lambda: head(0.9, 1.3)}
    st, drop, dz = p3['judgement']
    return {
        'idle': (*p3['idle'], PARTS),
        'attack': (*p3['attack'], PARTS),
        'judgement': (spread(st), drop, dz, judged),
        'rest': ({}, 0.0, 0.0, PARTS),
        'spread': (spread({}), 0.0, 0.0, PARTS),
    }


def cameras():
    """Round three's views, and close-ups of the wings in the rest pose (the rest and spread
    recipes share them): from the back quarter, the side and the front."""
    cams = A3.cameras()
    root = [WING_ROOT[0], S.HIP_Y+S.WAIST+WING_ROOT[1], WING_ROOT[2]]
    c = [0.0, root[1]+0.4, root[2]]
    for name, d in (('wing_back', [-0.55, 0.3, 0.8]), ('wing_side', [-1, 0.12, 0.05]),
                    ('wing_front', [-0.35, 0.2, -1])):
        ln = sum(v*v for v in d)**0.5
        cams.append({'name': name, 'eye': [round(c[k]+d[k]*10.5/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    return cams


def main():
    for name, (st, drop, dz, parts) in poses().items():
        H.write(HERE/f'angel_a4_{name}.asset.json',
                recipe(f'angel_a4_{name}', assemble(st, drop, dz, parts)))
    H.write(HERE/'cameras_a4.json', cameras())


if __name__ == '__main__':
    main()
