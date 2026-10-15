#!/usr/bin/env python3
"""Mech Expo 2000: Momentum's angel (MR-02), concept A, round 4b: the halo on its own joint, and
the spread wings' flight plates made to read.

Builds on round four (make_angel_a4.py, beside this script; it imports it) and changes two
things.

The halo joint. The halo leaves the head mesh for a part of its own on a new joint, `halo`, a
child of the head (the third new joint, after wing_l and wing_r). At rotation 0 it sits where
round four's halo sits and follows the head in every move carried over from Shadow; every other
joint keeps its offset.

  What a key can do: the Animation Kit's keys turn joints (`pose`: degrees per joint) and move
  only the root (`offset`, the pelvis); a joint's offset is the rig's and fixed, and nothing
  scales a part (docs/ANIMKIT.md, "Rigs" and the key table). So the halo can be lifted only by
  turning it, and grown not at all, without a new kit feature.

  The lift by turning: the joint's pivot is not the halo's centre but a point 0.45 m above it
  and 0.78 m behind it (HALO_PIVOT, in the head's frame), with the ring hung from it. Turning the
  joint 60 degrees about X (HALO_RAISED) swings the ring along an arc whose chord is vertical:
  it ends 0.9 m straight above where it started, its tilt changed from 30 degrees back to 30
  degrees forward (the head is thrown back 20 degrees in Judgement, so it ends nearly level).
  In between it rises along the arc, 0.39 m back at mid-swing. Range: x 0..60.

  The growth (1.3x) is the effect's: Judgement's effect already flares the halo, and
  anim_part() gives the halo joint's matrix, so the flare is drawn on the raised ring. The
  sheets show it with a stand-in (render_angel_a4b.py). Two meshes swapped by the effect would
  also do it, but the runtime draws one mesh a part per mech (AK_MESH), so that would be new
  runtime code.

The flight plates. Spread, the two chrome plates of each wing were nearly lost against the grey
sky. EDGES lists the treatments tried, each a Judgement recipe; the chosen one (EDGE) paints
the rest: the chrome kept, with a white strip along the long plate's trailing edge (two strips,
48 triangles).

1,892 triangles (round four 1,844; Shadow 1,800; the Hero 1,776).

Writes, beside this script: angel_a4b_{judgement,rest,raised}.asset.json (the raised is the
rest pose with only the halo raised, for its close-up), angel_a4b_edge_{0,1,2,3}.asset.json
(Judgement in each wing treatment; 0 is round four's) and cameras_a4b.json.
render_angel_a4b.py renders them and draws the sheets.
Run from anywhere: python3 carts/mechexpo/concepts/angel_a/make_angel_a4b.py (standard library
only).
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_angel_a4 as A4  # noqa: E402

A3, H, S, T, group, plate_yz = A4.A3, A4.H, A4.S, A4.T, A4.group, A4.plate_yz

# ---- the halo joint -----------------------------------------------------------------------------

# where round four's halo sits, in the head's frame: the helm's lift and the halo's place in it
HALO_CENTRE = [A3.HALO_AT[0], A3.HALO_AT[1]+A3.HELM_LIFT, A3.HALO_AT[2]]
HALO_PIVOT = [HALO_CENTRE[0], HALO_CENTRE[1]+0.45, HALO_CENTRE[2]+0.78]
HALO_RAISED = [60, 0, 0]


def head():
    """Round four's head without the halo."""
    nodes = copy.deepcopy(A3.head())
    helm = nodes[-1]
    helm['children'] = [n for n in helm['children'] if n['id'] != 'halo']
    return nodes


def halo():
    """The halo part: the ring hung from its joint's pivot, at round four's place and tilt."""
    at = [round(HALO_CENTRE[k]-HALO_PIVOT[k], 4) for k in range(3)]
    return [group('ring', [A3.halo()], at, A3.HALO_TILT)]


# ---- the flight plates ------------------------------------------------------------------------
# (name, the long plate's colour, the short plate's colour, the colour of a strip along the long
# plate's trailing edge, or None). A steel of the sky's value (tried first, #8a96aa) lost the
# plates altogether, so the treatments push the value away from the sky's, lighter or darker.
EDGES = {
    '0': ('round four: both chrome', A3.BASE['chrome'], A3.BASE['chrome'], None),
    '1': ('chrome, a white trailing edge', A3.BASE['chrome'], A3.BASE['chrome'],
          A3.BASE['white']),
    '2': ('chrome, a gold trailing edge', A3.BASE['chrome'], A3.BASE['chrome'], A3.BASE['gold']),
    '3': ('gunmetal long plate, chrome short plate', A3.BASE['frame'], A3.BASE['chrome'], None),
}
EDGE = '1'
# the strip: along flight_b's back edge from its root to the tip, (z, y) as FLIGHT_B
STRIP = [(1.75, -0.9), (2.0, -3.0), (1.9, -5.0), (1.55, -6.0), (1.6, -4.9), (1.68, -3.0),
         (1.5, -1.0)]


def wing(strip):
    """Round four's wing, the flight plates painted `flight_b` (the long one) and `flight_a`,
    and with `strip`, the strip on the long plate's trailing edge (both faces, 2 cm proud)."""
    plates = [
        plate_yz('covert', A4.COVERT, 0.1, 'covert', 'covert', 'covert_edge', [0.15, 0, 0]),
        group('fan_a', [plate_yz('flight_a', A4.FLIGHT_A, 0.08, 'flight_a', 'flight_a',
                                 'flight_a', [0.02, 0, 0])], None, [A4.FAN_A, 0, 0]),
        group('fan_b', [plate_yz('flight_b', A4.FLIGHT_B, 0.08, 'flight_b', 'flight_b',
                                 'flight_b', [-0.1, 0, 0])]
              + ([plate_yz('edge_strip', STRIP, 0.12, 'strip', 'strip', 'strip',
                           [-0.12, 0, 0])] if strip else []), None, [A4.FAN_B, 0, 0]),
    ]
    hinge = H.cyl_x('hinge', 0.3, 0.34, 4, 'frame', [0.0, 0, 0])
    return [hinge, group('folded', plates, None, A3.WING_TURN)]


def parts(edge=EDGE):
    strip = EDGES[edge][3] is not None
    return {**A4.PARTS, 'head': head, 'halo': halo, 'wing': lambda: wing(strip)}


def skeleton():
    """Round four's skeleton and the halo joint."""
    return A4.skeleton() + [('halo', 'head', [round(c, 4) for c in HALO_PIVOT], None, 'halo',
                             None)]


def assemble(stance, drop, dz, prts):
    """make_angel_a4.assemble with this skeleton."""
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
                 'children': H.geometry(part, side, prts) + [node(k) for k in kids.get(jid, [])],
                 'transform': T(None, stance.get(jid))}
        if rest:
            return {'id': f'{jid}_mount', 'op': 'group', 'children': [inner],
                    'transform': T([round(c, 4) for c in t], rest)}
        inner['transform'] = T([round(c, 4) for c in t], stance.get(jid))
        return inner
    return [node('pelvis')]


def recipe(name, nodes, edge=EDGE, budget=1900):
    _, long_, short, strip = EDGES[edge]
    mats = {**A3.materials(A4.SCHEME),
            'flight_a': {'color': short, 'smooth': True},
            'flight_b': {'color': long_, 'smooth': True},
            'strip': {'color': strip or A3.BASE['white']}}
    r = H.recipe(name, nodes, budget, 2048, materials=mats)
    r['materials'] = {k: v for k, v in mats.items() if k in H.used(nodes)}
    r['lighting'] = A3.LIGHTING
    return r


def judgement():
    """Round four's Judgement, the halo raised on its joint."""
    st, drop, dz, _ = A4.poses()['judgement']
    return {**st, 'halo': list(HALO_RAISED)}, drop, dz


def cameras():
    """Round four's views, and the halo close up in the rest pose (the rest and raised recipes
    share them): from the side and a front quarter, framed to take the raised ring too."""
    cams = A4.cameras()
    hr, hp = S.world_frames({}, 0.0)['head']
    c = H.add(hp, H.mv(hr, [0, HALO_CENTRE[1]+0.2, HALO_CENTRE[2]-0.3]))
    for name, d in (('halo_side', [-1, 0.1, 0]), ('halo_quarter', [-0.7, 0.35, -0.8])):
        ln = sum(v*v for v in d)**0.5
        cams.append({'name': name, 'eye': [round(c[k]+d[k]*5.5/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    return cams


def main():
    st, drop, dz = judgement()
    H.write(HERE/'angel_a4b_judgement.asset.json',
            recipe('angel_a4b_judgement', assemble(st, drop, dz, parts())))
    H.write(HERE/'angel_a4b_rest.asset.json',
            recipe('angel_a4b_rest', assemble({}, 0.0, 0.0, parts())))
    H.write(HERE/'angel_a4b_raised.asset.json',
            recipe('angel_a4b_raised', assemble({'halo': list(HALO_RAISED)}, 0.0, 0.0,
                                                parts())))
    for k in EDGES:
        H.write(HERE/f'angel_a4b_edge_{k}.asset.json',
                recipe(f'angel_a4b_edge_{k}', assemble(st, drop, dz, parts(k)), k))
    H.write(HERE/'cameras_a4b.json', cameras())


if __name__ == '__main__':
    main()
