#!/usr/bin/env python3
"""Mech Expo 2000: GAMMA (Heartland Atomic Company, HA-58), Heartland's echo of Beam, the gunner.

Heartland buys surplus and makes it work: Raikō's zoner rebuilt as a field-artillery and
civil-defence unit, boxy and a little battered, with a searchlight turned into a ray projector
(MOVES.md, "Decided by the owner (2026-10-14): Gamma, Heartland's ray gun"). The look is the
owner's chosen concept C, "military surplus" (concepts/gamma_c/make_gamma_c.py, which stays as the
record), refined here after the owner's notes on the comparison (mx-gamma-rig):

  the gun    read as a ray gun at fight size: the receiver moved back over the wrist so the
             slotted barrel shroud runs 2.55 m (2.3), the shroud in primer with dark slots (the
             light value band against the dark green), two cooling fins at its root; the lamp a
             bell-backed drum in 10 sides, 2.1 m across (1.84), in primer behind a dark bezel,
             the lens a green dome standing 0.24 m out of the bezel (seen side-on too, where the
             concept's flat lens was not), 1.6 m across its face behind the wire cross; the
             concept's hood over the drum is gone. The muzzle stays Beam's: (0, 0.8, -4.4) in
             weapon_r's frame, so the effects start where they did
  glows      one green, in three round-or-slatted places of one family: the gun's lens (the
             biggest), the reactor between the hatch's louvres (the meter's glow), and the
             searchlight head's lens, cut to a small lamp (0.3 m, from 0.46) recessed under its
             hood: the face's one eye, the same green as the gun's lens behind the same wire cross
  shield     the lead shield (weapon_l) in primer with the trefoil in dark green, its sides bent
             back like a field gun's shield wings and its top lip bent back, so swung out
             (SHIELD_OUT) it reads at fight size as a light slab in front of the fist, seen
             edge-on or not; stowed (weapon_l at 0, every phase-1 move) it lies along the outside
             of the left forearm
  details    the jerrycans' pressed X and the 58 stencils are gone (lost at fight size); the
             silhouette carries it: the searchlight drum on its yoke, the whip antenna (thicker),
             the primer pauldron on the right, the primer shin on the left, the racked cans

The skeleton is the Hero's (make_hero.skeleton), as Beam's is: the same part ids, joints and
guard (make_beam.STANCE), so Beam's moves play on it unchanged. weapon_r is the projector,
weapon_l the shield; no new joints.

Writes, beside this script: gamma.asset.json (assembled, in Beam's guard), gamma_rest.asset.json
(the rest pose), gamma_flex.asset.json (every joint bent far, for checking; not packed),
parts/gamma_*.asset.json (each part alone, its origin at its joint), gamma.rig.json,
cameras.json, cameras_flex.json and asset-preview.json (the preview's hangar look). Heartland's
emblem is Tank's (models/tank/heartland_emblem.png).
Run from anywhere: python3 carts/mechexpo/models/gamma/make_gamma.py (standard library only).
"""
import copy
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parent
for sub in ('hero', 'beam', 'tank'):
    sys.path.insert(0, str(MODELS/sub))
import make_hero as H  # noqa: E402
import make_beam as B  # noqa: E402
import make_tank as TK  # noqa: E402
import mxpaint as P  # noqa: E402

T, loft, crect, by_side, box = H.T, H.loft, H.crect, H.by_side, H.box
cyl_y, cyl_z = B.cyl_y, B.cyl_z

P.FONT.setdefault('8', ['01110', '10001', '10001', '01110', '10001', '10001', '01110'])

NAME = 'gamma'
SERIAL = 'HA-58'
BUDGET = 1950           # the assembled mech's triangle budget (the pack's MECH_LIMITS)

# ---- paint ------------------------------------------------------------------------------------
# Heartland's colours (make_tank.py): the greens, primer, one neutral metal (gunmetal), the dark
# of rubber and bores, the stencils' off-white, and the one green glow.

GREEN, GREEN_DK, PRIMER = TK.GREEN, TK.GREEN_DK, TK.PRIMER
GUN, DARK, CREAM = TK.GUN, TK.DARK, TK.CREAM
GLOW = '#8cff6e'

# The roles (the material names): concept C's scheme 1, "depot green".
#   hull     the main armour (green)          hull2   the second tone (dark green)
#   patch    replacement panels (primer)      worn    the hull, chipped (primer showing)
#   frame    joints, frame, gunmetal          can     the jerrycans (dark green)
#   kit      the toolbox (primer)             plate   the lead shield (primer)
#   lamp     the projector's drum (primer)    vents   the barrel shroud: primer, dark slots
ROLE = {'hull': GREEN, 'hull2': GREEN_DK, 'patch': PRIMER, 'frame': GUN, 'can': GREEN_DK,
        'kit': PRIMER, 'plate': PRIMER, 'lamp': PRIMER, 'dark': DARK}


def chips(field, chip, n=16):
    """An n x n tile of paint worn through: a few ragged flecks of `chip` on `field`."""
    pts = [(3, 4, 3, 2), (11, 10, 2, 1), (13, 2, 1, 1)]
    rows = [['0']*n for _ in range(n)]
    for x, y, w, h in pts:
        for j in range(h):
            for i in range(w):
                rows[(y+j) % n][(x+i) % n] = '1'
        rows[(y+h) % n][(x+1) % n] = '1'          # a ragged edge
    return {'texels': [''.join(r) for r in rows], 'colors': [field, chip]}


def slots(field, dark, n=16):
    """The barrel shroud's vent slots: a slot 10 texels long, 3 wide, in each n x n."""
    rows = []
    for j in range(n):
        rows.append(''.join('1' if 3 <= i < 13 and 6 <= j < 9 else '0' for i in range(n)))
    return {'texels': rows, 'colors': [field, dark]}


def trefoil(field, ink, w=32, h=32):
    """The radiation trefoil, stencilled: a dot and three blades, the top one pointing up."""
    s = [('disc', ink, (0.5, 0.5), 0.09)]
    for k in range(3):
        a0 = math.radians(270+120*k-30)
        pts = []
        for i in range(7):
            a = a0+math.radians(60)*i/6
            pts.append((0.5+0.44*math.cos(a), 0.5-0.44*math.sin(a)))
        for i in range(6, -1, -1):
            a = a0+math.radians(60)*i/6
            pts.append((0.5+0.15*math.cos(a), 0.5-0.15*math.sin(a)))
        s.append(('poly', ink, pts))
    return P.texels(s, w, h, field)


def materials():
    m = {role: {'color': c} for role, c in ROLE.items()}
    m['glow'] = {'color': GLOW, 'class': 'emissive'}
    m['worn'] = {'color': GREEN, 'texture': {**chips(GREEN, PRIMER), 'projection': 'box',
                                             'scale': [1.5, 1.5]}}
    m['vents'] = {'color': PRIMER, 'texture': {**slots(PRIMER, DARK), 'projection': 'cylindrical',
                                               'scale': [0.42, 0.42]}}
    for key, field in (('roundel', GREEN), ('roundel_p', PRIMER)):
        m[key] = {'color': field, 'texture': {
            **H.emblem_texture(TK.emblem_heartland(green=field, cream=CREAM, dark=GREEN_DK,
                                                   glow=GLOW), field), 'projection': 'fit'}}
    m['serial'] = {'color': PRIMER, 'texture': {**P.serial_plate(SERIAL, PRIMER, DARK),
                                                'projection': 'fit'}}
    m['trefoil'] = {'color': PRIMER, 'texture': {**trefoil(PRIMER, GREEN_DK), 'projection': 'fit'}}
    return m


MATERIALS = materials()
LIGHTING = H.LIGHTING
LOOK = {'background': ['#56647a', '#a4b0be'], 'ground': '#7a8592'}

# The Hero's material -> a role, for every part taken from the Hero (as make_beam.repaint does
# for Raikō); PER_NODE by node id, and PER_SIDE for the replaced parts on one side.
PAINT = {'red': 'hull', 'white': 'hull2', 'chrome': 'frame', 'frame': 'frame', 'dark': 'dark',
         'glow': 'glow', 'steel': 'frame', 'edge': 'glow', 'serial': 'serial',
         'hazard': 'worn'}
PER_NODE = {
    'skirt': {'chrome': 'hull2', 'red': 'worn'},
    'rear_skirt': {'red': 'hull2'},
    'gauntlet': {'white': 'hull', 'chrome': 'worn', 'red': 'hull'},
    'knee_guard': {'white': 'worn'},
    'back': {'red': 'hull2'},
    'thumb': {'red': 'hull2'},
    'instep': {'white': 'hull2'},
    'shoe': {'red': 'hull', 'white': 'hull2'},
}
# a replacement shin on the left: its plates in primer
PER_SIDE = {('shin', 'l'): {'red': 'patch', 'white': 'patch'}}


def repaint(nodes, side_over=None):
    nodes = copy.deepcopy(nodes)

    def walk(n, over):
        over = {**PER_NODE.get(n.get('id'), over), **(side_over or {})}

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


def hero_nodes(part, side=None, drop=()):
    return repaint([n for n in H.PARTS[part]() if n['id'] not in drop],
                   PER_SIDE.get((part, side)))


def group(id_, children, translate=None, rotate=None, scale=None, mirror=False):
    g = {'id': id_, 'op': 'group', 'children': children, 'transform': T(translate, rotate, scale)}
    if mirror:
        g['modifiers'] = [{'op': 'mirror', 'axis': 'x'}]
    return g


def plate_x(id_, outline, depth, mat, at, rotate=None, faces=None, decals=None):
    """A flat plate in the Y-Z plane, `depth` thick along X: `outline` as (z, y) points. An
    extrusion turned so its front face (+Z) looks along +X (outward on a left-side part)."""
    n = {'id': id_, 'op': 'extrude', 'depth': depth, 'material': mat,
         'points': [[round(-z, 4), round(y, 4)] for z, y in outline]}
    if faces:
        n['faces'] = faces
    if decals:
        n['decals'] = decals
    inner = {**n, 'transform': T(None, [0, 90, 0])}
    return group(f'{id_}_at', [inner], at, rotate)


def by_id(nodes, id_):
    return next(n for n in nodes if n['id'] == id_)


# ---- the parts (left / centre, origin at the joint) --------------------------------------------

def head(side=None):
    """A searchlight on a yoke. The drum lies fore and aft (its axis Z); its front cap is the
    rim, the lamp a small green lens recessed in it behind a wire guard (an upright bar and a
    crossbar) under a hood that juts like a brow, on a yoke whose arms hold it either side."""
    neck = cyl_y('neck', 0.34, 0.5, 4, 'frame', [0, 0.16, 0])
    yoke = box('yoke', [1.42, 0.2, 0.7], 'hull2', [0, 0.38, 0.0])
    arms = group('yoke_arms', [box('yoke_arm', [0.14, 0.62, 0.34], 'hull2', [0.68, 0.7, 0.0])],
                 mirror=True)
    lamp = cyl_z('lamp', 0.6, 1.16, 8, 'hull', [0, 0.92, 0.02],
                 faces={'bottom': 'frame', 'top': 'frame'})
    # the lens: a small drum standing just out of the rim, its face the eye
    lens = cyl_z('lens', 0.3, 0.1, 6, 'dark', [0, 0.92, -0.6], faces={'bottom': 'glow'})
    hood = box('hood', [1.36, 0.16, 0.7], 'hull2', [0, 1.5, -0.46], [-8, 0, 0])
    bars = [box('guard_bar', [0.08, 1.06, 0.08], 'frame', [0, 0.92, -0.74]),
            box('guard_cross', [1.06, 0.08, 0.08], 'frame', [0, 0.92, -0.8])]
    return [neck, yoke, arms, lamp, lens, hood, *bars]


REACTOR_Y, REACTOR_TILT = 2.1, -7.1     # the hatch on the chest's front, following its slope


def chest_face(y):
    """(z, the tilt) of the chest's front plane at height y (band 1, 1.7 to 2.5)."""
    return -1.10-(y-1.7)*0.125


def torso(side=None):
    """A boxy chest over the Hero's waist; the reactor hatch and the primer patch on the front;
    the rack, the cans, the toolbox and the antenna on the back."""
    hero = hero_nodes('torso')
    chest = loft('chest', 'y', [
        (0.9, crect(1.10, 0.76, 0.16, 0.14)),
        (1.7, crect(1.70, 1.04, 0.2, 0.18, oz=-0.06)),
        (2.5, crect(1.90, 1.12, 0.22, 0.18, oz=-0.08)),
        (3.08, crect(1.80, 1.06, 0.2, 0.18, oz=-0.04)),
        (3.42, crect(1.12, 0.82, 0.16, 0.14, oz=0.02)),
    ], by_side({0: {'*': 'hull2'},
                1: {'*': 'hull', 'b': 'hull2'},
                2: {'*': 'hull', 'fr': 'worn', 'fl': 'worn'},
                3: {'*': 'worn', 'b': 'hull2'}}),
        'frame', 'frame')
    collar = loft('collar', 'y', [
        (3.3, crect(0.74, 0.58, 0.14)),
        (3.66, crect(0.58, 0.46, 0.12)),
    ], lambda k, j: 'hull2', None, 'frame')

    def on_front(id_, children, x):
        z = chest_face(REACTOR_Y)
        return group(id_, children, [x, REACTOR_Y, round(z, 4)], [REACTOR_TILT, 0, 0])
    # the reactor hatch: a housing sunk into the sternum, glowing on its front and sides, three
    # louvre slats across it (front edges down), standing past its sides
    housing = box('housing', [1.1, 0.78, 0.5], 'frame', [0, 0, -0.1],
                  faces={'back': 'glow', 'left': 'glow', 'right': 'glow'}, open_=['front'])
    slats = [box(f'louvre_{k}', [1.28, 0.08, 0.28], 'frame', [0, y, -0.34], [-30, 0, 0])
             for k, y in enumerate((-0.22, 0.0, 0.22))]
    reactor = on_front('reactor', [housing, *slats], 0.0)
    patch = on_front('patch_panel', [box('patch', [0.74, 0.82, 0.12], 'patch', [0, 0, -0.04])],
                     1.12)
    return [by_id(hero, 'abdomen'), chest, by_id(hero, 'shoulder_sockets'), collar, reactor,
            patch] + back_rack()


def back_rack():
    """In place of Beam's reaction tanks: a rack on the back, two jerrycans on it, a toolbox
    under them and the whip antenna. (Concept C's can handles, strap and pintle hook are gone:
    lost at fight size, and 48 triangles.)"""
    rack = box('rack', [2.1, 2.3, 0.32], 'frame', [0, 2.3, 1.12])
    can = group('cans', [box('can', [0.5, 1.5, 1.08], 'can', [0.54, 2.74, 1.8])], mirror=True)
    toolbox = box('toolbox', [1.9, 0.62, 0.9], 'kit', [0, 1.72, 1.66], faces={'top': 'hull2'})
    # the whip: its base on the rack's top right corner, the rod raked back
    whip = group('whip', [box('whip_rod', [0.11, 3.9, 0.11], 'dark', [0, 1.75, 0])],
                 [-0.86, 3.4, 1.18], [16, 0, 0])
    return [rack, can, toolbox, whip]


def pauldron(side=None):
    """Beam's square block, Heartland's roundel on the outer face (the middle band's +X side,
    flat); the right one a replacement in primer; a chipped top."""
    face = 'patch' if side == 'r' else 'hull'
    mark = 'roundel_p' if side == 'r' else 'roundel'
    plate = loft('plate', 'y', [
        (0.92, crect(0.56, 0.62, 0.12, 0.12, ox=0.26)),
        (0.44, crect(0.94, 1.0, 0.18, 0.18, ox=0.44)),
        (-0.44, crect(0.94, 1.0, 0.18, 0.18, ox=0.44)),
        (-0.68, crect(0.80, 0.86, 0.16, 0.16, ox=0.46)),
    ], by_side({0: {'*': 'worn' if side != 'r' else face},
                1: {'*': face, 'r': mark, 'b': 'hull2', 'f': 'hull2'},
                2: {'*': 'hull2'}}),
        'frame', face)
    return [plate]


MUZZLE = B.MUZZLE           # (0, 0.8, -4.4): Beam's, so the effects start where they did
ROD = (0.0, 0.3, -4.86)     # the Rod Shot's bore, under the lens
SHROUD = (-0.85, -3.4)      # the slotted shroud runs from the receiver to the lamp's bell


def ring(r, n=10, y=0.0):
    """A circle of n points round (0, y), as (x, y) loft points for a loft along z."""
    return [(round(r*math.cos(2*math.pi*(k+0.5)/n), 4), round(y+r*math.sin(2*math.pi*(k+0.5)/n), 4))
            for k in range(n)]


def projector(side=None):
    """The nuclear ray projector (weapon_r), on Beam's mount and held as Beam holds the Arc
    Cannon: the grip up through the fist, the receiver on top, the barrel along -Z (the
    forearm's line). From the wrist out: the receiver (back over the wrist), a cooling fin, the
    slotted primer shroud, the lamp (a bell-backed drum in primer, 10-sided, a dark bezel round
    its front) with the lens standing out of the bezel as a glowing dome, its face at MUZZLE,
    behind its wire guard, and the Rod Shot's tube."""
    y = MUZZLE[1]
    z0 = MUZZLE[2]
    body = box('receiver', [1.0, 0.92, 1.7], 'hull', [0, y, 0.0],
               faces={'top': 'worn', 'front': 'hull2', 'back': 'hull2'})
    fin = cyl_z('fin', 0.66, 0.14, 6, 'frame', [0, y, SHROUD[0]-0.15])
    shroud = cyl_z('shroud', 0.42, SHROUD[0]-SHROUD[1]+0.15, 8, 'vents',      # its root in
                   [0, y, (SHROUD[0]+0.15+SHROUD[1])/2])                       # the receiver
    # the lamp, one loft: a bell from the shroud out to the drum (primer), the bezel (dark), and
    # the lens standing out of it, its face the glow at MUZZLE
    lamp = loft('lamp', 'z', [
        (SHROUD[1]+0.1, ring(0.5, y=y)),
        (z0+0.86, ring(0.96, y=y)),
        (z0+0.34, ring(1.05, y=y)),
        (z0+0.24, ring(1.02, y=y)),
        (z0, ring(0.8, y=y)),
    ], lambda k, j: ('lamp', 'lamp', 'frame', 'glow')[k], 'frame', 'glow')
    bars = [box('lens_bar', [0.1, 1.76, 0.1], 'frame', [0, y, z0-0.08]),
            box('lens_cross', [1.76, 0.1, 0.1], 'frame', [0, y, z0-0.14])]
    # the Rod Shot: a tube under the shroud in a jacket of its own, under the lamp, its bore
    # standing out under the lens
    tube = cyl_z('rod_tube', 0.16, 4.1, 6, 'frame', [0, ROD[1], ROD[2]+2.05],
                 faces={'bottom': 'dark'})
    jacket = box('rod_jacket', [0.42, 0.34, 1.9], 'hull2', [0, ROD[1], -2.0])
    return [body, fin, shroud, lamp, *bars, tube, jacket]


SHIELD_OUT = [0, 90, 0]      # weapon_l's key that swings the shield out in front of the fist


def shield(side=None):
    """The lead shield (weapon_l). Mount frame: +Y out of the fist's thumb side (up, with the
    forearm level), -Z along the forearm past the fist, +Z back toward the elbow, +X outward. The
    plate stands in the Y-Z plane outside the hand and forearm (stowed); a bracket holds it to
    the back of the fist. Turned SHIELD_OUT about Y it stands across the arm's line in front of
    the grip, its front face (the trefoil) looking along the forearm. A field gun's shield: the
    plate in primer, its top lip and its two side wings bent back (toward the mech when swung
    out), so it has depth seen edge-on."""
    outline = [(-0.8, -1.25), (1.95, -1.25), (1.95, 0.9), (1.65, 1.2), (-0.5, 1.2),
               (-0.8, 0.9)]
    plate = plate_x('plate', outline, 0.2, 'plate', [0.7, 0, 0],
                    faces={'side': 'frame'},
                    decals=[{'id': 'mark', 'face': 'front', 'material': 'trefoil',
                             'size': [1.2, 1.2], 'at': [0.6, -0.15]},
                            {'id': 'slit', 'face': 'front', 'material': 'dark',
                             'size': [0.9, 0.12], 'at': [0.45, 0.84]}])
    lip = plate_x('lip', [(-0.5, 0.0), (1.65, 0.0), (1.65, 0.4), (-0.5, 0.4)], 0.16, 'plate',
                  [0.7, 1.16, 0], [0, 0, 50], faces={'side': 'frame'})
    # the wings: the plate's two side edges bent back 40 degrees (toward -X: inward, behind it)
    wings = [plate_x(f'wing_{k}', [(-0.32, -1.2), (0.32, -1.2), (0.32, 0.9), (-0.32, 0.9)], 0.16,
                     'hull2', [0.5, 0, z], [0, sgn*40, 0], faces={'side': 'frame'})
             for k, (z, sgn) in enumerate(((2.2, -1), (-1.05, 1)))]
    bracket = box('bracket', [0.3, 0.6, 0.5], 'frame', [0.53, 0, 0.18])
    return [plate, lip, *wings, bracket]


def shared(part):
    return lambda side=None: hero_nodes(part, side)


PARTS = {
    'pelvis': shared('pelvis'), 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': shared('upper_arm'), 'forearm': shared('forearm'), 'hand': shared('hand'),
    'projector': projector, 'shield': shield,
    'thigh': shared('thigh'), 'shin': shared('shin'), 'foot': shared('foot'),
}
SIDED = H.SIDED
WEAPONS = {'r': 'projector', 'l': 'shield'}


def geometry(part, side):
    nodes = PARTS[part](side)
    if side == 'r':
        return [{'id': 'mirrored', 'op': 'group', 'children': nodes,
                 'transform': {'scale': [-1, 1, 1]}}]
    return nodes


def assemble(stance, drop):
    """The Hero's rig (make_hero.skeleton) as nested groups, with these parts; each weapon on its
    mount, turned by its own key inside the mount's rest rotation."""
    sk = H.skeleton(WEAPONS)
    kids = {}
    for jid, parent, *_ in sk:
        kids.setdefault(parent, []).append(jid)

    def node(jid):
        _, parent, offset, rest, part, side = next(e for e in sk if e[0] == jid)
        t = list(offset)
        if parent is None:
            t[1] -= drop
        g = {'id': jid, 'op': 'group',
             'children': geometry(part, side) + [node(k) for k in kids.get(jid, [])],
             'transform': T(None, stance.get(jid))}
        if rest:
            return {'id': f'{jid}_mount', 'op': 'group', 'children': [g],
                    'transform': T([round(c, 4) for c in t], rest)}
        g['transform'] = T([round(c, 4) for c in t], stance.get(jid))
        return g
    return [node('pelvis')]


def used(nodes):
    """The materials the nodes name, decals' included (make_hero.used, which has no decals)."""
    out = set(H.used(nodes))

    def walk(n):
        out.update(d['material'] for d in n.get('decals', []))
        for c in n.get('children', []):
            walk(c)
    for n in nodes:
        walk(n)
    return out


def recipe(name, nodes, budget, vertices=2048):
    r = H.recipe(name, nodes, budget, vertices, materials=MATERIALS)
    r['materials'] = {k: v for k, v in MATERIALS.items() if k in used(nodes)}
    r['lighting'] = LIGHTING
    return r


# ---- posing ----------------------------------------------------------------------------------

STANCE = dict(B.STANCE)         # Beam's guard: its moves start from it
DRAWN_DROP = B.DRAWN_DROP
FLEX = H.flex_pose()
FLEX_DROP = H.FLEX_DROP


def frames(stance, drop):
    """{joint: (rotation, position)} in the asset's frame, weapons' keys included."""
    out = {}
    for jid, parent, offset, rest, _, _ in H.skeleton(WEAPONS):
        r = H.rot(stance.get(jid, [0, 0, 0]))
        if rest:
            r = H.mm(H.rot(rest), r)
        if parent is None:
            out[jid] = (r, [offset[0], offset[1]-drop, offset[2]])
        else:
            pr, pt = out[parent]
            out[jid] = (H.mm(pr, r), H.add(pt, H.mv(pr, offset)))
    return out


def muzzle_world(stance, drop):
    """MUZZLE and the barrel's direction in the asset's frame, for a pose."""
    r, p = frames(stance, drop)['weapon_r']
    return H.add(p, H.mv(r, list(MUZZLE))), H.mv(r, [0, 0, -1])


# ---- cameras ---------------------------------------------------------------------------------

def aim(name, centre, d, dist):
    ln = math.sqrt(H.dot(d, d))
    return {'name': name, 'eye': [round(centre[k]+d[k]*dist/ln, 3) for k in range(3)],
            'target': [round(c, 3) for c in centre]}


def cameras(stance, drop):
    """Side views at game distance (31.2 m: about 80 px of 240), nearer ones, quarters, the head
    and the reactor hatch close up in the rest pose, the projector and the stowed shield in the
    guard, and each fist."""
    mid, mz = 5.8, -2.0
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_facing_left', 'eye': [31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_right_near', 'eye': [-17.0, 6.6, mz], 'target': [0, 6.6, mz]},
        {'name': 'side_left_near', 'eye': [17.0, 6.6, mz], 'target': [0, 6.6, mz]},
        {'name': 'front_quarter', 'eye': [-13.0, 10.0, -16.5], 'target': [0, 7.6, -1.0]},
        {'name': 'back_quarter', 'eye': [12.5, 10.5, 15.5], 'target': [0, 7.6, 0.5]},
        {'name': 'front', 'eye': [0, 8.6, -21.0], 'target': [0, 7.6, 0]},
    ]
    rest = frames({}, 0.0)
    hr, hp = rest['head']
    hc = H.add(hp, H.mv(hr, [0, 0.9, -0.1]))
    cams += [aim('head_side', hc, [-1, 0.05, -0.55], 4.6),
             aim('head_quarter', hc, [-0.75, 0.3, -0.8], 4.6)]
    tr, tp = rest['torso']
    rc = H.add(tp, H.mv(tr, [0, REACTOR_Y, chest_face(REACTOR_Y)]))
    cams += [aim('reactor_quarter', rc, [-0.55, 0.25, -1], 5.5),
             aim('reactor_side', rc, [-1, 0.1, -0.2], 5.5),
             aim('back_close', H.add(tp, H.mv(tr, [0, 2.4, 1.6])), [-0.8, 0.45, 1], 7.0)]
    fr = frames(stance, drop)
    wr, wp = fr['weapon_r']
    gc = H.add(wp, H.mv(wr, [0, 0.8, -2.0]))
    cams += [aim('gun_side', gc, [-1, 0.2, 0.05], 6.5),
             aim('gun_quarter', gc, [-0.7, 0.35, -0.8], 6.5)]
    lr, lp = fr['weapon_l']
    sc = H.add(lp, H.mv(lr, [0.7, 0, 0.57]))
    cams += [aim('shield_stowed', sc, [1, 0.2, -0.3], 5.5)]
    return cams + H.grip_cameras(stance, drop, WEAPONS)


# ---- writing ---------------------------------------------------------------------------------

def height():
    """The rest pose's top (from the assembled recipe's bounds)."""
    return H.part_facts(recipe('h', assemble({}, 0.0), 4000))['bounds']['max'][1]


def main():
    H.write(HERE/f'{NAME}.asset.json', recipe(NAME, assemble(STANCE, DRAWN_DROP), BUDGET))
    H.write(HERE/f'{NAME}_rest.asset.json', recipe(f'{NAME}_rest', assemble({}, 0.0), BUDGET))
    written = {}
    for part in PARTS:
        for side in (('l', 'r') if part in SIDED else (None,)):
            pname = H.part_name(NAME, part, side)
            r = recipe(pname, geometry(part, side), 400, 512)
            H.write(HERE/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    # parts no longer made (a renamed part) must not linger for the pack to pick up
    for p in (HERE/'parts').glob(f'{NAME}_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    H.write(HERE/f'{NAME}_flex.asset.json', recipe(f'{NAME}_flex', assemble(FLEX, FLEX_DROP),
                                                   BUDGET))
    H.write(HERE/'cameras.json', cameras(STANCE, DRAWN_DROP))
    H.write(HERE/'cameras_flex.json', H.flex_cameras(FLEX, FLEX_DROP, WEAPONS))
    H.write(HERE/'asset-preview.json', LOOK)
    rig = H.write_rig(HERE, NAME, STANCE, DRAWN_DROP, WEAPONS, written)
    h = round(height(), 3)
    rig['body'] = ("Heartland Atomic Company's Gamma (HA-58): Beam's frame on the Hero's skeleton, "
                   'refitted from army surplus: weapon_r the ray projector (held as Beam holds '
                   'the Arc Cannon), weapon_l the lead shield')
    rig['height'] = h
    rig['muzzle'] = {'part': 'weapon_r', 'at': list(MUZZLE),
                     'note': "the projector's lens, in weapon_r's frame: Beam's effect point"}
    rig['shield'] = {'part': 'weapon_l', 'out': list(SHIELD_OUT),
                     'note': 'weapon_l at 0 is the shield stowed along the left forearm; at '
                             "'out' it is swung out in front of the fist (Lead Shielding)"}
    H.write(HERE/f'{NAME}.rig.json', rig)
    print(f'{NAME}: {rig["triangles"]} triangles, {h} m tall')


if __name__ == '__main__':
    main()
