#!/usr/bin/env python3
"""Mech Expo 2000: the Double-blade Hero (Umbral Research), production pass.

Umbral's echo of the Hero: Momentum's frame, bought or copied by a secretive lab and rebuilt
for speed. The rig, the joints and most limbs and the torso are the Hero's own, taken from
../hero/make_hero.py (imported, not copied), so the two cannot drift apart; this script swaps
the paint and the pieces Umbral changed:

  head      the Hero's helmet (the same sections, two more in the visor band for a slit), its jaw
            and crest; Umbral's narrower, meaner brow, hood wings swept back and down, small
            violet roundels
  torso     the Hero's, without Momentum's flywheel: an antimatter containment ring in its place
  pauldron  new: slimmer, lighter plates swept back
  dagger    new: two short blades, one in each hand, in a normal grip
  legs      rebuilt for speed: slimmer thighs, shins with a calf pod, a swept fin and a thruster,
            long pointed feet with a heel spur (the same joints)
  arms      the Hero's, lightened: smaller drums, a gauntlet of three sections
  the rest  the Hero's parts, repainted: black, lighter graphite plates and violet edging (so the
            shape reads at game distance), darker joints, smoked violet metal

The trade-show finish is Umbral's: its eclipse emblem on the pauldrons, a serial plate on each
thigh (UR-02) and violet-and-black hazard stripes round the ankles.

Writes, beside this script: doubleblade.asset.json (assembled, in its rushdown stance),
doubleblade_rest.asset.json (rest pose), doubleblade_flex.asset.json (every joint bent far, for
checking; not packed), parts/doubleblade_*.asset.json (each part alone, its origin at its joint),
doubleblade.rig.json, cameras.json, cameras_flex.json and umbral_emblem.png (the mark for the
menus). Run from anywhere: python3 carts/mechexpo/models/doubleblade/make_doubleblade.py
"""
import copy
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'hero'))
import make_hero as H  # noqa: E402
import mxpaint as P  # noqa: E402

# ---- paint (STYLE.md: Umbral Research is black and violet) ----------------------------------

MATERIALS = {
    'black':    {'color': '#2a2733'},
    'graphite': {'color': '#8a83a4'},          # the Hero's white plates: light enough to read
    'violet':   {'color': '#9a52f5'},          # trim and edging
    'smoke':    {'color': '#8a80a8', 'smooth': True},   # smoked, violet-tinted metal for chrome
    'frame':    {'color': '#36333f'},          # darker joints
    'dark':     {'color': '#141219'},
    'blade':    {'color': '#625a7e'},          # the blades' flats
    'vglow':    {'color': '#c47cff', 'class': 'emissive'},   # visor slit, antimatter core
    'vedge':    {'color': '#e8c8ff', 'class': 'emissive'},   # the blades' edges
    'emblem':   {'color': '#26232f', 'texture': {
        **P.texels(P.scaled(P.emblem_umbral(violet='#9a52f5', black='#26232f'), 26/64, 26/32,
                            19/64, 3/32), 64, 32, '#26232f'), 'projection': 'fit'}},
    'serial':   {'color': '#756e8e', 'texture': {**P.serial_plate('UR-02', '#756e8e', '#141219'),
                                                 'projection': 'fit'}},
    'hazard':   {'color': '#9a52f5', 'texture': {**P.hazard(['#9a52f5', '#141219']),
                                                 'projection': 'box', 'scale': [0.32, 0.32]}},
}

# The Hero's material -> Umbral's, for every repainted part; PER_NODE overrides it by node id.
PAINT = {'red': 'black', 'white': 'graphite', 'chrome': 'smoke', 'frame': 'frame',
         'dark': 'dark', 'glow': 'vglow', 'steel': 'blade', 'edge': 'vedge'}
PER_NODE = {
    'gauntlet': {'white': 'violet', 'chrome': 'violet'},    # forearm stripe and cuff
    'shin': {'chrome': 'violet'},                           # the band above the ankle
    'skirt': {'chrome': 'violet', 'red': 'graphite'},       # the side skirts: edges, flanks
    'crest': {'red': 'violet'},                             # the Hero's crest, Umbral's colour
}


def repaint(nodes):
    """A deep copy of the Hero's nodes with Umbral's materials."""
    nodes = copy.deepcopy(nodes)

    def walk(n, over):
        over = PER_NODE.get(n.get('id'), over)

        def m(name):
            return over.get(name, PAINT.get(name, name))
        if 'material' in n:
            n['material'] = m(n['material'])
        if 'face_materials' in n:
            n['face_materials'] = [m(x) for x in n['face_materials']]
        if isinstance(n.get('faces'), dict):
            n['faces'] = {k: m(v) for k, v in n['faces'].items()}
        for c in n.get('children', []):
            walk(c, over)
    for n in nodes:
        walk(n, {})
    return nodes


def hero_nodes(part, drop=()):
    """The Hero's part, repainted, without the nodes named in `drop`."""
    return repaint([n for n in H.PARTS[part]() if n['id'] not in drop])


def by_id(nodes, id_):
    return next(n for n in nodes if n['id'] == id_)


loft, crect, by_side, cyl_x, box, T = H.loft, H.crect, H.by_side, H.cyl_x, H.box, H.T


# ---- Umbral's pieces --------------------------------------------------------------------------

def head():
    hero = hero_nodes('head')
    # the same helmet, with two more sections in the visor band (on the same surface: crect is
    # linear in its numbers) so only a slit of it glows
    spec = H.HELMET_SPEC
    a, b = spec[1], spec[2]

    def lerp(t):
        return tuple(a[i]+(b[i]-a[i])*t for i in range(6))
    secs = [spec[0], a, lerp(0.25), lerp(2/3)] + spec[2:]
    helmet = loft('helmet', 'y', [(y, crect(w, d, cf, cb, oz=oz))
                                  for y, w, d, cf, cb, oz in secs],
                  by_side({0: {'*': 'black', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                           2: {'*': 'black', 'f': 'vglow', 'fr': 'vglow', 'fl': 'vglow'},
                           '*': {'*': 'black'}}),
                  'frame', 'black')
    # a narrower brow that dips in the middle over the slit: a scowl from the front, a beak
    # pointing down from the side
    brow = H.chevron('brow', 'graphite',
                     [(-0.5, 0.77), (-0.98, 0.74), (-0.9, 0.9), (-0.5, 1.16)],
                     [(-0.5, 0.86), (-0.72, 0.86), (-0.7, 0.96), (-0.5, 1.12)], 0.45)
    # the wings swept back and down along the head, a hood; violet on their edges
    hood = {'id': 'hood', 'op': 'group', 'children': [
        {'id': 'hood_wing', 'op': 'extrude', 'depth': 0.12, 'material': 'graphite',
         'faces': {'side': 'violet'},
         'points': [[0.30, 0.95], [0.30, 1.36], [1.38, 0.98], [1.12, 0.70]],
         'transform': {'pivot': [0.31, 1.16, 0], 'rotate': [0, -58, 0],
                       'translate': [0, 0, -0.1]}}],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    # Umbral's mark: small violet roundels in smoked rims, higher and further back
    marks = cyl_x('marks', 0.17, 1.36, 6, 'smoke', [0, 0.96, 0.16],
                  faces={'top': 'violet', 'bottom': 'violet'})
    neck = dict(by_id(hero, 'neck'), segments=4)      # hidden under the collar: 12 triangles
    return [neck, helmet, brow, by_id(hero, 'jaw'), by_id(hero, 'crest'),
            hood, marks]


def ring_mesh(id_, centre, r_out, r_in, width, seg, mat_side, mat_out, mat_in):
    """A hoop around the X axis (a square section), centred at `centre`."""
    m = H.Mesh()
    cx, cy, cz = centre
    hw = width/2
    v = []
    for i in range(seg):
        a = 2*math.pi*(i+0.5)/seg
        c, s = math.cos(a), math.sin(a)
        v.append([m.vert((cx+x, cy+r*c, cz+r*s)) for r in (r_out, r_in) for x in (-hw, hw)])
    for i in range(seg):
        p, q = v[i], v[(i+1) % seg]
        a = 2*math.pi*(i+1)/seg
        radial = [0, math.cos(a), math.sin(a)]
        # outer, inner, -X side, +X side; corners: 0 out-x, 1 out+x, 2 in-x, 3 in+x
        for idx, mat, want in (([p[0], p[1], q[1], q[0]], mat_out, radial),
                               ([p[2], p[3], q[3], q[2]], mat_in, H.mul(radial, -1)),
                               ([p[0], p[2], q[2], q[0]], mat_side, [-1, 0, 0]),
                               ([p[1], p[3], q[3], q[1]], mat_side, [1, 0, 0])):
            for tri in ((idx[0], idx[1], idx[2]), (idx[0], idx[2], idx[3])):
                m.poly(list(tri), mat, want)
    return m.node(id_)


def diamond(id_, centre, r, h, seg, mat):
    """A bipyramid along Y: the antimatter core, a diamond seen from any side."""
    m = H.Mesh()
    cx, cy, cz = centre
    ring = [m.vert((cx+r*math.sin(2*math.pi*i/seg), cy, cz+r*math.cos(2*math.pi*i/seg)))
            for i in range(seg)]
    top, bot = m.vert((cx, cy+h/2, cz)), m.vert((cx, cy-h/2, cz))
    for i in range(seg):
        a, b = ring[i], ring[(i+1) % seg]
        for tip in (top, bot):
            tri = [a, b, tip]
            m.poly(tri, mat, H.sub(H.cent([m.v[k] for k in tri]), list(centre)))
    return m.node(id_)


RING_AT = (0.0, 2.3, 1.85)


def torso():
    nodes = hero_nodes('torso', drop=('flywheel', 'hub'))
    # two-tone chest: black front and back, graphite flanks, violet edges on the lower chamfers
    trim(by_id(nodes, 'chest'), 8, {(1, 'r'): 'graphite', (1, 'l'): 'graphite',
                                    (2, 'r'): 'graphite', (2, 'l'): 'graphite',
                                    (0, 'fr'): 'violet', (0, 'fl'): 'violet',
                                    (1, 'br'): 'violet', (1, 'bl'): 'violet'})
    # an antimatter containment ring where Momentum's flywheel was: a dark hoop, round from the
    # side, around a glowing violet core
    hoop = ring_mesh('containment_ring', RING_AT, 1.08, 0.74, 0.46, 8, 'black', 'smoke',
                     'violet')
    core = diamond('antimatter_core', RING_AT, 0.36, 1.0, 6, 'vglow')
    return nodes + [hoop, core]


def pauldron():
    """Lighter than the Hero's: narrower, shallower, swept back from its top edge."""
    # the outer side's middle band is flat (the same x and the same z span at both sections, the
    # second further back): a parallelogram carrying Umbral's emblem
    plate = loft('plate', 'y', [
        (0.72, crect(0.36, 0.42, 0.14, 0.12, ox=0.2, oz=0.02)),
        (0.30, crect(0.62, 0.66, 0.22, 0.30, ox=0.32, oz=0.26)),
        (-0.22, crect(0.56, 0.64, 0.18, 0.30, ox=0.38, oz=0.52)),
        (-0.38, crect(0.46, 0.50, 0.14, 0.2, ox=0.38, oz=0.6)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'r': 'emblem', 'fr': 'graphite', 'br': 'graphite'},
                2: {'*': 'violet'}}),
        'frame', 'black')
    return [plate]


def dagger():
    """One short blade. Local frame as the Hero's sword: the grip's middle at the origin, the
    blade along +Y, its width along Z, its flats facing +-X."""
    grip = {'id': 'grip', 'op': 'cylinder', 'radius': 0.13, 'height': 0.95, 'segments': 4,
            'material': 'dark', 'transform': T([0, -0.04, 0])}
    pommel = {'id': 'pommel', 'op': 'cone', 'radius': 0.17, 'height': 0.42, 'segments': 4,
              'material': 'smoke', 'transform': T([0, -0.68, 0], [180, 45, 0])}
    sec = [(0.16, 0.44), (0.24, 0.53), (0.16, 0.62), (-0.16, 0.62), (-0.24, 0.53),
           (-0.16, 0.44)]

    def small(f):
        return [(x*f, 0.53+(y-0.53)*f) for x, y in sec]
    # a guard swept forward at both ends, like a pair of claws
    guard = loft('guard', 'z', [
        (-0.62, [(x, y+0.14) for x, y in small(0.5)]),
        (0.0, sec),
        (0.62, [(x, y+0.14) for x, y in small(0.5)]),
    ], lambda k, j: 'black', 'violet', 'violet')

    def blade_sec(hw, ht, flat):
        return [(0.0, hw), (ht, flat), (ht, -flat), (0.0, -hw), (-ht, -flat), (-ht, flat)]

    def bmat(k, j):
        return 'blade' if j in (1, 4) else 'vedge'
    blade = loft('blade', 'y', [
        (0.6, blade_sec(0.30, 0.08, 0.1)),
        (2.5, blade_sec(0.32, 0.075, 0.1)),
    ], bmat, 'blade', None, tip=((0.0, 3.3, 0.16), lambda j: bmat(0, j)))
    return [grip, pommel, guard, blade]


def trim(node, n, table):
    """Repaint faces of a loft node (made by H.loft, `n` points a section) by band and side:
    {(band, side name): material}. Bands' faces come first in the node, two triangles a side."""
    fm = node['face_materials']
    for (k, side), mat in table.items():
        j = H.SIDES.index(side)
        for t in (0, 1):
            fm[(k*n+j)*2+t] = mat
    return node


def side_extrude(id_, pts, depth, mat, side_mat, x=0.0):
    """A plate in the Y-Z plane (seen whole from the side), pts as (z, y), `depth` thick in X,
    centred on x."""
    return {'id': id_, 'op': 'extrude', 'depth': depth, 'material': mat,
            'faces': {'side': side_mat}, 'points': [[-z, y] for z, y in pts],
            'transform': {'rotate': [0, 90, 0], 'translate': [x, 0, 0]}}


def upper_arm():
    drum = cyl_x('shoulder_drum', 0.48, 0.72, 6, 'frame', [0, 0, 0])
    arm = loft('arm', 'y', [
        (-0.3, crect(0.32, 0.34, 0.12)),
        (-1.95, crect(0.28, 0.31, 0.1)),
    ], lambda k, j: 'frame', None, 'frame')
    return [drum, arm]


def forearm():
    """The Hero's gauntlet in three sections, slimmer, with violet edges on its front corners."""
    drum = cyl_x('elbow_drum', 0.36, 0.6, 6, 'smoke', [0, 0, 0])
    arm = loft('gauntlet', 'y', [
        (-0.3, crect(0.36, 0.38, 0.14)),
        (-1.15, crect(0.46, 0.52, 0.18, oz=0.04)),
        (-1.85, crect(0.38, 0.42, 0.14, oz=0.02)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet', 'r': 'graphite'},
                1: {'*': 'black', 'fr': 'violet', 'fl': 'violet'}}),
        'black', 'frame')
    guard = loft('elbow_guard', 'x', [
        (-0.35, [(0.22, 0.42), (0.62, 0.1), (0.56, -0.6), (0.3, -0.72)]),
        (0.35, [(0.22, 0.42), (0.62, 0.1), (0.56, -0.6), (0.3, -0.72)]),
    ], lambda k, j: 'violet' if j == 1 else 'graphite', 'graphite', 'graphite')
    return [drum, arm, guard]


def thigh():
    """Slimmer than the Hero's, violet edges down its front corners; the serial plate outside."""
    drum = cyl_x('hip_drum', 0.48, 0.6, 6, 'smoke', [0, 0, 0])
    edge = {'fr': 'violet', 'fl': 'violet'}
    arm = loft('thigh', 'y', [
        (-0.32, crect(0.42, 0.50, 0.16)),
        (-0.92, crect(0.50, 0.58, 0.2, oz=-0.06)),
        (-1.42, crect(0.50, 0.58, 0.2, oz=-0.06)),
        (-2.2, crect(0.40, 0.46, 0.16)),
        (-2.42, crect(0.36, 0.42, 0.14)),
    ], by_side({0: {'*': 'black', **edge}, 1: {'*': 'black', 'r': 'serial', **edge},
                2: {'*': 'black', **edge}, 3: {'*': 'frame'}}),
        'frame', 'frame')
    return [drum, arm]


def shin():
    """Rebuilt for speed: a spiked knee guard, a calf pod swept back with a fin and a thruster
    under it, and the Hero's skirt round the ankle (violet hazard stripes)."""
    drum = cyl_x('knee_drum', 0.42, 0.8, 6, 'frame', [0, 0, 0])
    spike = [(-0.22, 0.78), (-0.78, 0.18), (-0.64, -0.45), (-0.4, -0.75), (-0.2, -0.45)]
    knee = loft('knee_guard', 'x', [(-0.44, spike), (0.44, spike)],
                lambda k, j: 'violet' if j == 0 else 'graphite', 'graphite', 'graphite')
    leg = loft('shin', 'y', [
        (-0.4, crect(0.44, 0.48, 0.16, oz=0.06)),
        (-1.2, crect(0.54, 0.86, 0.2, 0.42, oz=0.34)),
        (-2.0, crect(0.52, 0.68, 0.2, 0.3, oz=0.14)),
        (-2.3, crect(0.52, 0.62, 0.18, 0.24, oz=0.04)),
        (-2.68, crect(0.50, 0.60, 0.16, 0.22, oz=0.0)),
    ], by_side({0: {'*': 'black', 'f': 'graphite', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'f': 'graphite', 'fr': 'violet', 'fl': 'violet'},
                2: {'*': 'smoke'},
                3: {'*': 'frame', 'r': 'hazard', 'l': 'hazard'}}),
        'frame', 'frame')
    fin = side_extrude('calf_fin', [(0.9, -0.55), (1.55, -0.05), (1.36, -0.5), (0.96, -1.45)],
                       0.12, 'black', 'violet')
    thruster = {'id': 'thruster', 'op': 'cone', 'radius': 0.26, 'height': 0.5, 'segments': 5,
                'material': 'smoke', 'faces': {'bottom': 'vglow'},
                'transform': T([0, -1.92, 0.78], [-24, 0, 0])}
    return [drum, knee, leg, fin, thruster]


def foot():
    """Longer and pointed, with a heel spur swept back; the Hero's instep plate."""
    drum = cyl_x('ankle_drum', 0.4, 0.78, 6, 'frame', [0, 0, 0])
    prof = [(0.7, -0.85), (0.8, -0.5), (0.3, -0.15), (-0.5, -0.32), (-1.5, -0.6),
            (-2.0, -0.8), (-1.6, -0.86)]
    smat = ['black', 'black', 'graphite', 'graphite', 'violet', 'dark', 'dark']
    shoe = loft('shoe', 'x', [(-0.56, prof), (0.56, prof)], lambda k, j: smat[j], 'black', 'black')
    tongue = [(-0.86, -0.38), (-0.5, 0.1), (-0.14, 0.18), (-0.02, -0.2)]
    instep = loft('instep', 'x', [(-0.34, tongue), (0.34, tongue)],
                  lambda k, j: 'violet' if j == 0 else 'smoke', 'smoke', 'smoke')
    spur = side_extrude('heel_spur', [(0.5, -0.45), (1.25, -0.72), (0.62, -0.8)], 0.16,
                        'violet', 'black')
    return [drum, shoe, instep, spur]


def shared(part):
    return lambda: hero_nodes(part)


PARTS = {
    'pelvis': shared('pelvis'), 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': shared('hand'),
    'dagger': dagger, 'thigh': thigh, 'shin': shin, 'foot': foot,
}
WEAPONS = {'r': 'dagger', 'l': 'dagger'}

# ---- the stance: lower, leaning in, both blades forward ---------------------------------------

DROP = 1.05
STANCE = H.pose({
    'pelvis': [-8, -6, 0],
    'torso': [-16, -8, 0],
    'head': [18, 8, 0],
    'thigh_r': [40, 0, -7], 'thigh_l': [-12, 0, 7],
    'upper_arm_r': [42, 0, -12], 'forearm_r': [52, 0, 4], 'hand_r': [-24, 0, 0],
    'upper_arm_l': [26, 0, 16], 'forearm_l': [82, 0, -6], 'hand_l': [-34, 0, 0],
}, DROP)
# The pitched pelvis leaves the soles a little off level, a toe 1.4 cm into the floor: the
# mech is drawn 2 cm higher than the knees were solved for.
DRAWN_DROP = DROP - 0.02


def main():
    H.write_mech(HERE, 'doubleblade', STANCE, DRAWN_DROP, PARTS, H.SIDED, WEAPONS, MATERIALS)
    # the head close-ups from a little above and nearer, so the blades held out in front do
    # not cover the face
    views = (('head_front', [0, 0.3, -1]), ('head_side_right', [-1, 0.25, 0]),
             ('head_side_left', [1, 0.25, 0]), ('head_three_quarter', [-0.75, 0.4, -0.7]))
    H.write(HERE/'cameras.json', H.camera_set(STANCE, DRAWN_DROP, head_dist=4.2, head_views=views)
            + H.grip_cameras(STANCE, DRAWN_DROP, WEAPONS))
    H.write_flex(HERE, 'doubleblade', PARTS, WEAPONS, MATERIALS)
    H.write_emblem(HERE/'umbral_emblem.png', P.emblem_umbral())


if __name__ == '__main__':
    main()
