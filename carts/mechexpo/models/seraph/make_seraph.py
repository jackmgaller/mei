#!/usr/bin/env python3
"""Mech Expo 2000: Seraph (Momentum Robotics), the paladin: MR-02, Momentum's echo of Shadow.

Umbral made a dark copy of Momentum's Hero (the Double-blade Hero); Momentum answers with a holy
copy of Umbral's Shadow, an angel on Momentum's kinetic power: an honest boxer where Shadow is a
trickster (MOVES.md, "Seraph"). The look is the owner's approved concept A, round 4b
(concepts/angel_a/make_angel_a4b.py, built on make_angel_a4.py and make_angel_a3.py, which stay
there as the record of the rounds); its code is moved here, unchanged in what it makes:

  paint      the "Gauntlets" scheme: white plates on a dark gunmetal frame; red on what strikes
             (the forearm cuffs and the fists), on the armour's edges (the pauldrons' lower tier,
             the knee guards, the codpiece) and on the solid upper wing plates; chrome flight
             plates with a white strip along the long plate's trailing edge (treatment 1); gold
             only on the halo, the crest and temple wings, the core's setting and the knuckles
  pelvis     a red codpiece, front plates (faulds) and side skirts over the gunmetal hips
  torso      a broad breastplate over a narrow waist, the red kinetic core in a gold setting on the
             sternum, a chrome collar, the wing pack on the back
  head       a knight's helm on a longer neck: the white visor slit glowing in a dark face under a
             jutting brow, a chrome chin guard, a gold blade crest, a gold wing at each temple
  pauldron   a big rounded two-tier shoulder shell, Momentum's mark on its outer panel
  upper_arm  the gunmetal frame
  forearm    a heavy bracer flaring to a wide red cuff, an elbow guard behind
  hand       the gauntlet fist, wrist to knuckles 1.2 m (Shadow's hand), so Shadow's arm keys
             reach the same places
  weapon_*   the knuckle guard: a gold band round the fist's end, on Shadow's claw mount (the
             knuckles; its +Y out of them), one mesh for both fists
  thigh, shin, foot   a plated thigh (the MR-02 plate outside), a pointed red knee guard, a flared
             greave and the ankle skirt (red hazard stripes), a pointed sabaton
  wing_*     each wing a part on its own joint: a hinge drum, the red upper wing plate (the
             covert, its arch over the shoulder) and two chrome flight plates fanned under it
  halo       the gold halo on its own joint, hung from a pivot above and behind it

The skeleton is Shadow's (make_shadow.skeleton: the shared enum Part, Shadow's joint offsets), so
Shadow's moves play on it unchanged, with three joints appended to the shared skeleton
(anim.akr's enum Part, tools/animkit/rig.py's PARTS):

  wing_l   parent torso, offset (0.82, 2.72, 0.95): the root high on the back at the side of the
           wing pack; its frame is the torso's (no rest rotation), folded at rotation 0.
           Spread (WING_SPREAD) is x -122, y 50, z -24. Range x -130..10, y -10..130, z -35..10:
           y past 65 only for the Wing Ward's wrap (WING_WARD, about 120: the plates swung round
           the sides to the front)
  wing_r   parent torso, offset (-0.82, 2.72, 0.95): the left one mirrored (y and z negated)
  halo     parent head, its pivot 0.45 m above and 0.78 m behind the ring (HALO_PIVOT): turning
           it x 0..60 swings the ring up an arc whose chord is vertical, 0.9 m straight up at 60
           (HALO_RAISED), its tilt from 30 degrees back to 30 forward

At rotation 0 the wings are folded and the halo sits on the helm. The rig's guard is Seraph's
own, a boxer's (STANCE: upright, the right fist leading at chin height, the left by the jaw);
its sink is Shadow's with the weapon joints at 0 (a fist does not open).

1,892 triangles (Shadow 1,800, the Hero 1,776): three parts more than the others.

Writes, beside this script: seraph.asset.json (assembled, in its guard), seraph_rest.asset.json
(the rest pose), seraph_flex.asset.json (every joint bent far, the wings spread and the halo
raised, for checking; not packed), parts/seraph_*.asset.json (each part alone, its origin at its
joint), seraph.rig.json, cameras.json, cameras_flex.json and asset-preview.json (the preview's
hangar look). Helpers come from ../hero/make_hero.py (and mxpaint.py, Momentum's mark) and the
skeleton from ../shadow/make_shadow.py.
Run from anywhere: python3 carts/mechexpo/models/seraph/make_seraph.py (standard library only).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'shadow'))
sys.path.insert(0, str(HERE.parent/'hero'))
import make_hero as H  # noqa: E402
import make_shadow as S  # noqa: E402
import mxpaint as P  # noqa: E402

T, loft, crect, by_side, cyl_x, box = H.T, H.loft, H.crect, H.by_side, H.cyl_x, H.box
plate_yz = S.plate_yz

# ---- paint ----------------------------------------------------------------------------------------
# Momentum's red and white flipped (white body, red accents), chrome trim, gold for the holy parts,
# and a dark gunmetal frame so the white has something to stand against.

BASE = {
    'white':  '#ffffff',
    'red':    '#e01e26',
    'chrome': '#c6d0dc',
    'gold':   '#e8b030',
    'frame':  '#3a4150',
    'dark':   '#1c2029',
}
SMOOTH = {'chrome', 'gold'}

# The roles: what each surface is, and its colour in the chosen scheme ("Gauntlets", round three's
# scheme 1, with round four's solid red upper wing: the covert red on both faces, edged white).
SCHEME = {
    'armour': 'white', 'helm': 'white', 'chest': 'white', 'yoke': 'white', 'core': 'red',
    'core_rim': 'gold', 'collar': 'chrome', 'waist': 'frame', 'pack': 'frame',
    'pauldron': 'white', 'pauldron_rim': 'red', 'bicep': 'frame', 'bracer': 'white',
    'cuff': 'red', 'elbow': 'chrome', 'fist': 'red', 'knuckles': 'gold',
    'codpiece': 'red', 'skirt': 'white', 'skirt_edge': 'white', 'thigh': 'white', 'knee': 'red',
    'shin': 'white', 'shin_front': 'white', 'ankle': 'frame', 'foot': 'white', 'toe': 'white',
    'covert': 'red', 'covert_edge': 'white', 'lining': 'frame', 'crest': 'gold',
    'temple': 'gold', 'chin': 'chrome', 'frame': 'frame', 'joint': 'chrome', 'dark': 'dark',
}
GLOW, HALO = '#f4fbff', '#ffd659'
SERIAL_FIELD, SERIAL_INK = '#e4e7ec', BASE['dark']


def materials():
    m = {}
    for role, c in SCHEME.items():
        m[role] = {'color': BASE[c]}
        if c in SMOOTH:
            m[role]['smooth'] = True
    m['glow'] = {'color': GLOW, 'class': 'emissive'}
    m['halo'] = {'color': HALO, 'class': 'emissive'}
    pf = BASE[SCHEME['pauldron']]
    m['emblem'] = {'color': pf, 'texture': {
        **H.emblem_texture(P.emblem_momentum(red=BASE['red'], white=BASE['white']), pf),
        'projection': 'fit'}}
    m['serial'] = {'color': SERIAL_FIELD, 'texture': {
        **P.serial_plate('MR-02', SERIAL_FIELD, SERIAL_INK), 'projection': 'fit'}}
    m['hazard'] = {'color': BASE['red'], 'texture': {
        **P.hazard([BASE['red'], BASE[SCHEME['ankle']]]), 'projection': 'box',
        'scale': [0.32, 0.32]}}
    # the flight plates (treatment 1): chrome, and the white strip on the long plate's edge
    m['flight_a'] = {'color': BASE['chrome'], 'smooth': True}
    m['flight_b'] = {'color': BASE['chrome'], 'smooth': True}
    m['strip'] = {'color': BASE['white']}
    return m


MATERIALS = materials()

# White comes out grey under the cart's ambient (0.66) on the flanks the side camera sees; the
# concept's second round found 0.8 reads white against the hangar. The direction is the cart's.
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.8}
LOOK = {'background': ['#56647a', '#a4b0be'], 'ground': '#7a8592'}

# ---- the skeleton: Shadow's, and the wings and the halo ---------------------------------------

KNUCKLE = S.KNUCKLE                 # wrist to the knuckles (the weapon mount): -1.2
SHOULDER = S.SHOULDER
WING_ROOT = (0.82, 2.72, 0.95)      # the left wing's joint, in the torso's frame
WING_TURN = [5, -10, -7]            # the folded plates' turn in the wing's frame: trailing edge
                                    # in toward the spine, top out
WING_SPREAD = [-122, 50, -24]       # the left wing spread; the right's is mirrored (y, z negated)
WING_WARD = [-20, 120, 0]           # the Wing Ward's wrap: the left wing swung round the side to
                                    # the front (sp_d); the right's mirrored

HALO_AT, HALO_TILT = [0, 2.42, 0.34], [-30, 0, 0]  # the ring in the helm's frame
HELM_LIFT = 0.16                                    # the helm raised on its longer neck
HALO_CENTRE = [HALO_AT[0], HALO_AT[1]+HELM_LIFT, HALO_AT[2]]      # in the head's frame
HALO_PIVOT = [HALO_CENTRE[0], HALO_CENTRE[1]+0.45, HALO_CENTRE[2]+0.78]
HALO_RAISED = [60, 0, 0]            # the ring 0.9 m straight above where it sits

# What each part is and how far its joint should turn (written into the rig for the animators):
# Shadow's, with Seraph's parts named, and the three new joints.
RANGES = {
    **S.RANGES,
    'pelvis':    ('the gunmetal hips, the red codpiece, the faulds and side skirts', S.RANGES['pelvis'][1]),
    'torso':     ('the broad breastplate on the narrow waist, the red core, the chrome collar and '
                  'the wing pack (the wings are parts of their own)', S.RANGES['torso'][1]),
    'head':      ('the helm on its long neck: the visor slit, the gold crest and temple wings '
                  '(the halo is a part of its own)', S.RANGES['head'][1]),
    'pauldron':  ("the two-tier shoulder shell, Momentum's mark outside; follows the upper arm part "
                  'way', "about 0.35 of the upper arm's x and 0.5 of its z"),
    'upper_arm': ('the gunmetal upper arm', S.RANGES['upper_arm'][1]),
    'forearm':   ('the bracer, the red cuff and the elbow guard', S.RANGES['forearm'][1]),
    'hand':      ("the gauntlet fist (wrist to knuckles 1.2 m, Shadow's hand); the knuckle guard "
                  'mounts at its knuckles', S.RANGES['hand'][1]),
    'weapon':    ('the knuckle guard: a gold band round the fist\'s end; its +Y runs out of the '
                  'knuckles (the weapon joint: keep it at 0, the fist does not open)', 'x, y and z 0'),
    'wing':      ('the wing: the red upper wing plate and two chrome flight plates, folded at 0; '
                  'its frame is the torso\'s', 'left x -130..10, y -10..130, z -35..10 (the right '
                  'mirrored: y and z negated); spread is x -122, y 50, z -24; y past 65 only '
                  'for the Wing Ward\'s wrap, about x -20, y 120, z 0: the plates round the sides '
                  'to the front'),
    'halo':      ('the gold halo, hung from a pivot 0.45 m above and 0.78 m behind it: turning it '
                  'about x lifts it (60: 0.9 m straight up, tilted 30 degrees forward)', 'x 0..60'),
}

# ---- the parts (left / centre, origin at the joint) --------------------------------------------


def group(id_, children, translate=None, rotate=None, scale=None):
    return {'id': id_, 'op': 'group', 'children': children,
            'transform': T(translate, rotate, scale)}


def pelvis():
    """The hip block (gunmetal), a red codpiece pointing down at the front, two front plates
    (faulds) angled out over the thighs' tops, side skirts outside the hip drums, a rear plate."""
    core = loft('core', 'y', [
        (0.5, crect(0.62, 0.5, 0.18)),
        (0.0, crect(0.74, 0.56, 0.22, 0.18)),
        (-0.8, crect(0.3, 0.36, 0.1, oz=-0.04)),
    ], by_side({'*': {'*': 'frame'}}), 'frame', 'frame')
    cod = loft('codpiece', 'z', [
        (-0.74, [(0.0, -0.95), (0.3, -0.45), (0.34, 0.42), (-0.34, 0.42), (-0.3, -0.45)]),
        (-0.52, [(0.0, -1.05), (0.4, -0.5), (0.44, 0.5), (-0.44, 0.5), (-0.4, -0.5)]),
    ], lambda k, j: 'codpiece', 'codpiece', 'frame')
    fauld = group('faulds', [group('fauld', [
        plate_yz('fauld_plate', [(-0.42, 0.0), (0.38, 0.0), (0.3, -1.05), (-0.25, -1.25)], 0.1,
                 'skirt', 'frame', 'skirt_edge', [0, 0, 0])],
        [0.66, 0.42, -0.52], [0, 62, 12])])
    fauld['modifiers'] = [{'op': 'mirror', 'axis': 'x'}]
    side = group('side_skirts', [
        plate_yz('side_skirt', [(-0.62, 0.0), (0.58, 0.0), (0.42, -1.3), (-0.5, -1.25)], 0.12,
                 'skirt', 'frame', 'skirt_edge', [1.36, 0.42, 0.0], [0, 0, 10])])
    side['modifiers'] = [{'op': 'mirror', 'axis': 'x'}]
    rear = box('rear_skirt', [1.2, 0.95, 0.14], 'skirt', [0, -0.1, 0.62], [-14, 0, 0],
               faces={'front': 'frame'})
    return [core, cod, fauld, side, rear]


CORE_Y = 2.25


def torso():
    """A broad breastplate over a narrow waist; the red core on the sternum; the wing pack on the
    back (the wings hang from their own joints at its sides)."""
    waist = loft('waist', 'y', [
        (-0.32, crect(0.42, 0.38, 0.12)),
        (1.0, crect(0.56, 0.48, 0.16)),
    ], by_side({0: {'*': 'waist'}}), 'waist', None)
    chest = loft('chest', 'y', [
        (0.85, crect(0.72, 0.56, 0.2, 0.16)),
        (1.7, crect(1.24, 0.84, 0.36, 0.24, oz=-0.08)),
        (2.5, crect(1.46, 0.92, 0.42, 0.28, oz=-0.1)),
        (3.08, crect(1.3, 0.82, 0.36, 0.24, oz=-0.04)),
        (3.42, crect(0.72, 0.56, 0.2, 0.16)),
    ], by_side({0: {'*': 'chest', 'b': 'frame', 'br': 'frame', 'bl': 'frame'},
                1: {'*': 'chest'},
                2: {'*': 'chest', 'f': 'yoke', 'fr': 'yoke', 'fl': 'yoke'},
                3: {'*': 'yoke', 'b': 'frame', 'br': 'frame', 'bl': 'frame'}}),
        'frame', 'frame')
    setting = {'id': 'core_setting', 'op': 'cylinder', 'radius': 0.44, 'height': 0.24,
               'segments': 6, 'material': 'core_rim',
               'transform': T([0, CORE_Y, -0.98], [90, 0, 30])}
    gem = {'id': 'core', 'op': 'cylinder', 'radius': 0.3, 'height': 0.2, 'segments': 6,
           'material': 'core', 'faces': {'side': 'core_rim'},
           'transform': T([0, CORE_Y, -1.08], [90, 0, 30])}
    collar = loft('collar', 'y', [
        (3.3, crect(0.6, 0.5, 0.18)),
        (3.62, crect(0.5, 0.42, 0.14)),
    ], lambda k, j: 'collar', None, 'frame')
    pack = box('wing_pack', [1.5, 1.45, 0.8], 'pack', [0, 2.55, 0.96], [-6, 0, 0])
    return [waist, chest, setting, gem, collar, pack]


# ---- the wings ----------------------------------------------------------------------------------
# In the wing joint's frame (the torso's axes, the origin at the root): three plates in its own
# Y-Z plane, outlines as (z, y), +z back, turned by WING_TURN. The upper wing (the covert) is a
# big red shape, its arch rising over the shoulder; the two chrome flight plates under it are
# fanned at the root (the lower one swung 14 degrees back, the upper 4 forward), so folded the
# wing trails a clean double point behind the calves and spread the plates open into a fan.

COVERT = [(-0.28, -0.3), (-0.34, 0.75), (-0.02, 1.5), (0.5, 1.92), (1.0, 1.76), (1.36, 1.0),
          (1.52, -0.6), (1.42, -2.2), (1.16, -3.1), (0.5, -1.6)]
FLIGHT_A = [(0.1, 0.3), (0.85, 0.95), (1.45, 0.4), (1.75, -1.3), (1.7, -3.4), (1.4, -4.5),
            (0.85, -1.8)]
FLIGHT_B = [(0.3, -0.2), (1.15, 0.2), (1.75, -0.9), (2.0, -3.0), (1.9, -5.0), (1.55, -6.0),
            (1.0, -3.0)]
FAN_A, FAN_B = 4, -14
# the white strip along the long plate's trailing edge, from its root to the tip, (z, y)
STRIP = [(1.75, -0.9), (2.0, -3.0), (1.9, -5.0), (1.55, -6.0), (1.6, -4.9), (1.68, -3.0),
         (1.5, -1.0)]


def wing():
    """The left wing, in its joint's frame: the hinge drum and the folded plates."""
    plates = [
        plate_yz('covert', COVERT, 0.1, 'covert', 'covert', 'covert_edge', [0.15, 0, 0]),
        group('fan_a', [plate_yz('flight_a', FLIGHT_A, 0.08, 'flight_a', 'flight_a', 'flight_a',
                                 [0.02, 0, 0])], None, [FAN_A, 0, 0]),
        group('fan_b', [plate_yz('flight_b', FLIGHT_B, 0.08, 'flight_b', 'flight_b', 'flight_b',
                                 [-0.1, 0, 0]),
                        plate_yz('edge_strip', STRIP, 0.12, 'strip', 'strip', 'strip',
                                 [-0.12, 0, 0])], None, [FAN_B, 0, 0]),
    ]
    hinge = cyl_x('hinge', 0.3, 0.34, 4, 'frame', [0.0, 0, 0])
    return [hinge, group('folded', plates, None, WING_TURN)]


def halo_ring(r=0.72, tube=0.1, seg=10):
    """A gold ring (emissive), its axis +Y, centred at the origin, a triangular section."""
    m = H.Mesh()
    rings = []
    sec = ((tube, -tube*0.5), (0.0, tube*0.9), (-tube, -tube*0.5))
    for i in range(seg):
        a = 2*math.pi*i/seg
        c, s = math.cos(a), math.sin(a)
        rings.append([m.vert((c*(r+dr), dy, s*(r+dr))) for dr, dy in sec])
    n = len(sec)
    for i in range(seg):
        r0, r1 = rings[i], rings[(i+1) % seg]
        a = 2*math.pi*(i+0.5)/seg
        mid = [math.cos(a)*r, 0.0, math.sin(a)*r]
        for j in range(n):
            q = [r0[j], r0[(j+1) % n], r1[(j+1) % n], r1[j]]
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                m.poly(list(tri), 'halo', H.sub(H.cent([m.v[k] for k in tri]), mid))
    return m.node('halo_ring')


def halo():
    """The halo part: the ring hung from its joint's pivot, where the helm carried it, tilted
    back."""
    at = [round(HALO_CENTRE[k]-HALO_PIVOT[k], 4) for k in range(3)]
    return [group('ring', [halo_ring()], at, HALO_TILT)]


def head():
    """A knight's helm: white, a dark face band with the white visor slit standing proud of it
    under a jutting brow, a pointed chin guard, a gold blade crest on the brow, a small swept-back
    wing at each temple (the halo is its own part)."""
    neck = {'id': 'neck', 'op': 'cylinder', 'radius': 0.28, 'height': 0.8, 'segments': 4,
            'material': 'frame', 'transform': T([0, 0.3, 0], [0, 45, 0])}
    helm = loft('helm', 'y', [
        (0.25, crect(0.34, 0.4, 0.12, 0.1, oz=0.02)),
        (0.58, crect(0.44, 0.5, 0.16, 0.14)),
        (0.98, crect(0.46, 0.54, 0.18, 0.16, oz=0.02)),
        (1.3, crect(0.4, 0.5, 0.16, 0.16, oz=0.06)),
        (1.48, crect(0.22, 0.34, 0.08, 0.1, oz=0.1)),
    ], by_side({0: {'*': 'helm', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                1: {'*': 'helm', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                2: {'*': 'helm'}, 3: {'*': 'helm'}}),
        'frame', 'helm')
    visor = H.chevron('visor', 'glow',
                      [(-0.5, 0.73), (-0.64, 0.75), (-0.64, 0.83), (-0.5, 0.85)],
                      [(-0.44, 0.75), (-0.52, 0.76), (-0.52, 0.82), (-0.44, 0.83)], 0.4)
    brow = H.chevron('brow', 'helm',
                     [(-0.5, 0.9), (-0.8, 0.93), (-0.7, 1.08), (-0.46, 1.2)],
                     [(-0.46, 0.92), (-0.6, 0.94), (-0.56, 1.04), (-0.44, 1.14)], 0.46)
    chin = H.chevron('chin', 'chin',
                     [(-0.4, 0.26), (-0.7, 0.36), (-0.62, 0.6), (-0.42, 0.62)],
                     [(-0.38, 0.3), (-0.5, 0.36), (-0.5, 0.58), (-0.4, 0.6)], 0.36)
    blade = [(-0.58, 1.02), (-0.78, 1.42), (-0.66, 1.86), (-0.42, 1.32)]
    crest = loft('crest', 'x', [(-0.07, blade), (0.07, blade)],
                 lambda k, j: 'crest', 'crest', 'crest')
    temple = group('temples', [
        plate_yz('temple_wing', [(-0.2, 0.8), (0.35, 0.88), (1.3, 1.8), (0.55, 1.45),
                                 (-0.15, 1.22)], 0.1, 'temple', 'temple', 'crest',
                 [0.5, 0, 0], [0, 0, 8])])
    temple['modifiers'] = [{'op': 'mirror', 'axis': 'x'}]
    return [neck, group('helm_raised', [helm, visor, brow, chin, crest, temple],
                        [0, HELM_LIFT, 0])]


def pauldron():
    """The two-tier shoulder shell; its outer panel (the second band's +X side: the same x and
    z extents at both sections) carries Momentum's mark."""
    shell = loft('shell', 'y', [
        (0.72, crect(0.46, 0.6, 0.2, 0.2, ox=0.32)),
        (0.44, crect(0.74, 0.86, 0.3, 0.3, ox=0.46)),
        (-0.14, crect(0.74, 0.86, 0.3, 0.3, ox=0.46)),
        (-0.42, crect(0.68, 0.8, 0.26, 0.26, ox=0.46)),
    ], by_side({0: {'*': 'pauldron'}, 1: {'*': 'pauldron', 'r': 'emblem'},
                2: {'*': 'pauldron_rim'}}),
        'pauldron', 'frame')
    rim = loft('rim', 'y', [
        (-0.3, crect(0.6, 0.76, 0.24, 0.24, ox=0.5)),
        (-0.78, crect(0.5, 0.7, 0.2, 0.2, ox=0.58)),
    ], by_side({'*': {'*': 'pauldron_rim'}}), 'frame', 'frame')
    return [shell, rim]


def upper_arm():
    drum = cyl_x('shoulder_drum', 0.36, 0.66, 6, 'frame', [0, 0, 0])
    arm = loft('arm', 'y', [
        (-0.25, crect(0.28, 0.3, 0.09)),
        (-2.35, crect(0.24, 0.26, 0.08)),
    ], lambda k, j: 'bicep', None, 'frame')
    return [drum, arm]


def forearm():
    """The bracer: heavy, flaring from the elbow to a wide cuff; an elbow guard behind."""
    drum = cyl_x('elbow_drum', 0.3, 0.54, 6, 'elbow', [0, 0, 0])
    arm = loft('bracer', 'y', [
        (-0.24, crect(0.28, 0.3, 0.09)),
        (-1.6, crect(0.42, 0.48, 0.14, oz=0.03)),
        (-2.05, crect(0.48, 0.54, 0.16, oz=0.03)),
        (-2.5, crect(0.44, 0.5, 0.15, oz=0.03)),
    ], by_side({0: {'*': 'bracer'}, 1: {'*': 'cuff'}, 2: {'*': 'cuff'}}),
        'frame', 'frame')
    guard = [(0.18, 0.4), (0.5, 0.12), (0.62, -0.5), (0.34, -0.78)]
    elbow = loft('elbow_guard', 'x', [(-0.2, guard), (0.2, guard)],
                 lambda k, j: 'bracer', 'bracer', 'bracer')
    return [drum, arm, elbow]


def hand():
    """The gauntlet fist: wrist to knuckles 1.2 m (Shadow's hand), broad fore and aft (the side
    camera sees it whole), the fingers curled under on the palm side (-X), the thumb over them at
    the front (-Z)."""
    wrist = cyl_x('wrist', 0.24, 0.44, 4, 'joint', [0, 0, 0])
    fist = loft('fist', 'y', [
        (-0.12, crect(0.28, 0.38, 0.08)),
        (-0.5, crect(0.42, 0.56, 0.14, 0.14)),
        (KNUCKLE-0.04, crect(0.38, 0.52, 0.12, 0.12)),
    ], by_side({0: {'*': 'fist'}, 1: {'*': 'fist', 'l': 'frame', 'fl': 'frame', 'bl': 'frame'}}),
        'frame', 'fist')
    fingers = box('fingers', [0.3, 0.72, 0.96], 'frame', [-0.26, -0.84, 0.0])
    thumb = box('thumb', [0.38, 0.32, 0.3], 'fist', [-0.12, -0.7, -0.56])
    return [wrist, fist, fingers, thumb]


def knuckle_guard():
    """The weapon part (on Shadow's claw mount, at the knuckles): a gold band round the fist's
    end. Its frame: +Y out of the knuckles, the hand's +Z is its -Z."""
    band = loft('knuckle_band', 'y', [
        (-0.3, crect(0.46, 0.62, 0.14)),
        (0.02, crect(0.46, 0.62, 0.14)),
        (0.14, crect(0.32, 0.56, 0.12)),
    ], lambda k, j: 'knuckles', 'knuckles', 'knuckles')
    return [band]


def thigh():
    """Plated: white over the front and sides, the gunmetal frame behind; the serial plate on the
    outside (the second band's +X side, flat)."""
    drum = cyl_x('hip_drum', 0.4, 0.56, 6, 'joint', [0, 0, 0])
    back = {'b': 'frame', 'br': 'frame', 'bl': 'frame'}
    arm = loft('thigh', 'y', [
        (-0.3, crect(0.42, 0.48, 0.14)),
        (-0.95, crect(0.5, 0.56, 0.17, oz=-0.04)),
        (-1.6, crect(0.5, 0.56, 0.17, oz=-0.04)),
        (-2.6, crect(0.34, 0.4, 0.12)),
    ], by_side({0: {'*': 'thigh', **back}, 1: {'*': 'thigh', 'r': 'serial', **back},
                2: {'*': 'thigh', **back}}),
        'frame', 'frame')
    return [drum, arm]


def shin():
    """A pointed knee guard, a greave flaring at the calf, the ankle skirt running past the ankle
    joint so a pitched foot turns inside it."""
    drum = cyl_x('knee_drum', 0.36, 0.7, 4, 'frame', [0, 0, 0])
    prof = [(-0.24, 0.72), (-0.72, 0.26), (-0.64, -0.6), (-0.3, -0.78)]
    knee = loft('knee_guard', 'x', [(-0.4, prof), (0.4, prof)],
                lambda k, j: 'knee', 'knee', 'knee')
    leg = loft('greave', 'y', [
        (-0.3, crect(0.34, 0.4, 0.12, oz=0.04)),
        (-1.3, crect(0.46, 0.6, 0.16, 0.22, oz=0.1)),
        (-2.62, crect(0.46, 0.54, 0.16, 0.16, oz=0.02)),
        (-3.08, crect(0.44, 0.52, 0.15, 0.15)),
    ], by_side({0: {'*': 'shin', 'f': 'shin_front', 'fr': 'shin_front', 'fl': 'shin_front',
                    'b': 'frame'},
                1: {'*': 'shin', 'f': 'shin_front', 'fr': 'shin_front', 'fl': 'shin_front'},
                2: {'*': 'ankle', 'r': 'hazard', 'l': 'hazard'}}),
        'frame', 'frame')
    return [drum, knee, leg]


def foot():
    """A pointed sabaton; the instep rises into the shin's skirt."""
    drum = cyl_x('ankle_drum', 0.34, 0.66, 6, 'frame', [0, 0, 0])
    prof = [(0.62, -0.77), (0.68, -0.42), (0.28, -0.08), (-0.5, -0.28), (-1.5, -0.57),
            (-2.0, -0.77), (-1.55, -0.8)]
    smat = ['foot', 'foot', 'foot', 'foot', 'toe', 'dark', 'dark']
    shoe = loft('sabaton', 'x', [(-0.44, prof), (0.44, prof)], lambda k, j: smat[j], 'foot',
                'foot')
    return [drum, shoe]


PARTS = {
    'pelvis': pelvis, 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': hand, 'knuckle': knuckle_guard,
    'thigh': thigh, 'shin': shin, 'foot': foot, 'wing': wing, 'halo': halo,
}
SIDED = {'pauldron', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot', 'wing'}


def geometry(part, side):
    return H.geometry(part, side, PARTS)


# ---- the skeleton, posing, assembling --------------------------------------------------------

def skeleton():
    """(id, parent, offset, rest rotation, part, side), parents first: Shadow's skeleton (its ids,
    order and offsets) with the knuckle guards on the claws' mounts, then the three joints
    appended to the shared skeleton: wing_l, wing_r (the torso's) and halo (the head's)."""
    out = []
    for jid, parent, offset, rest, part, side in S.skeleton():
        out.append((jid, parent, offset, rest, 'knuckle' if part == 'claw' else part, side))
    x, y, z = WING_ROOT
    return out + [('wing_l', 'torso', [x, y, z], None, 'wing', 'l'),
                  ('wing_r', 'torso', [-x, y, z], None, 'wing', 'r'),
                  ('halo', 'head', [round(c, 4) for c in HALO_PIVOT], None, 'halo', None)]


def world_frames(stance, drop=0.0):
    """{joint id: (rotation, position)} in the asset's frame."""
    out = {}
    for jid, parent, offset, rest, _, _ in skeleton():
        r = H.rot(stance.get(jid, [0, 0, 0]))
        if rest:
            r = H.mm(H.rot(rest), r)
        if parent is None:
            out[jid] = (r, [offset[0], offset[1]-drop, offset[2]])
        else:
            pr, pt = out[parent]
            out[jid] = (H.mm(pr, r), H.add(pt, H.mv(pr, offset)))
    return out


def assemble(stance, drop=0.0):
    """The rig as nested groups, posed. A joint's rest rotation (the knuckle guards') comes before
    its pose: a group for the rest, the posed group inside it."""
    sk = skeleton()
    kids = {}
    for jid, parent, *_ in sk:
        kids.setdefault(parent, []).append(jid)

    def node(jid):
        _, parent, offset, rest, part, side = next(e for e in sk if e[0] == jid)
        t = list(offset)
        if parent is None:
            t[1] -= drop
        inner = {'id': jid, 'op': 'group',
                 'children': geometry(part, side) + [node(k) for k in kids.get(jid, [])],
                 'transform': T(None, stance.get(jid))}
        if rest:
            return {'id': f'{jid}_mount', 'op': 'group', 'children': [inner],
                    'transform': T([round(c, 4) for c in t], rest)}
        inner['transform'] = T([round(c, 4) for c in t], stance.get(jid))
        return inner
    return [node('pelvis')]


def recipe(name, nodes, budget, vertices=2048):
    r = H.recipe(name, nodes, budget, vertices, materials=MATERIALS)
    r['materials'] = {k: v for k, v in MATERIALS.items() if k in H.used(nodes)}
    r['lighting'] = LIGHTING
    return r


def fists(stance):
    """A stance with the weapon joints at 0: the knuckle guards sit square on the fists."""
    return {**stance, 'weapon_r': [0, 0, 0], 'weapon_l': [0, 0, 0]}


def spread(stance):
    return {**stance, 'wing_l': list(WING_SPREAD), 'wing_r': [WING_SPREAD[0], -WING_SPREAD[1],
                                                              -WING_SPREAD[2]]}


# ---- the guard: a boxer's, upright, fists up (MOVES.md, "Seraph", "For the animators") --------
# The right side leads, as Shadow's and the Hero's: the right foot forward, the body bladed (the
# right shoulder turned in). Upright where Shadow crouches, the knees soft; the right fist leads at
# chin height about 3 m out, the left by the jaw, both elbows in under the shoulders and the
# forearms near upright, the chin tucked behind the lead fist. The wings folded, the halo down.
# Every one of Seraph's moves starts and ends here.

GUARD_DROP = 1.15
STANCE = fists(S.pose({
    'pelvis': [0, -10, 0], 'torso': [-6, -12, 0], 'head': [8, 12, 0],
    'thigh_r': [30, 0, -8], 'thigh_l': [-22, 0, 8],
    'upper_arm_r': [16, -10, 4], 'forearm_r': [124, 0, -4], 'hand_r': [14, 0, 0],
    'upper_arm_l': [4, 24, -10], 'forearm_l': [144, 0, 10], 'hand_l': [14, 0, 0],
}, GUARD_DROP))
DRAWN_DROP = GUARD_DROP - 0.03
# The sink is Shadow's (its placeholder moves used it), the fists closed.
SINK = fists(S.SINK)
SINK_DROP = S.SINK_DROP
# The flex check: Shadow's, the halo raised, the left wing at the far end of its range (swung up,
# out and back past the spread) and the right one at the near end (swung in and down).
FLEX = {**fists(S.FLEX), 'halo': list(HALO_RAISED), 'wing_l': [-130, 65, -35], 'wing_r': [10, 10, 10]}
FLEX_DROP = S.FLEX_DROP


# ---- cameras ---------------------------------------------------------------------------------

def cameras(stance, drop):
    """Side views at game distance (31.2 m: about 80 px), nearer ones, quarters, the head close
    up, each fist, and the wings and the halo in the rest pose."""
    mid, mz = 5.8, -2.0
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_facing_left', 'eye': [31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_right_near', 'eye': [-17.0, 6.5, mz], 'target': [0, 6.5, mz]},
        {'name': 'side_left_near', 'eye': [17.0, 6.5, mz], 'target': [0, 6.5, mz]},
        {'name': 'front_quarter', 'eye': [-12.0, 9.5, -16.0], 'target': [0, 6.5, -1.5]},
        {'name': 'back_quarter', 'eye': [12.0, 10.0, 14.0], 'target': [0, 7.0, 0.0]},
        {'name': 'front', 'eye': [0, 7.0, -20.0], 'target': [0, 6.5, 0]},
        {'name': 'back_close', 'eye': [-7.5, 10.5, 9.0], 'target': [0, 7.5, 1.2]},
    ]
    fr = world_frames(stance, drop)
    hr, hp = fr['head']
    hc = H.add(hp, H.mv(hr, [0, 0.95+HELM_LIFT, -0.2]))
    for name, dv in (('head_front', [0, 0.25, -1]), ('head_side_right', [-1, 0.2, 0]),
                     ('head_side_left', [1, 0.2, 0]), ('head_three_quarter', [-0.75, 0.35, -0.7])):
        v = H.mv(hr, dv)
        ln = math.sqrt(H.dot(v, v))
        cams.append({'name': name, 'eye': [round(hc[k]+v[k]*4.6/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in hc]})
    for sd, sx in (('r', -1), ('l', 1)):
        r, p = fr[f'hand_{sd}']
        c = H.add(p, H.mv(r, [0, -0.75, 0]))
        for name, dv in (('out', [sx, 0.2, 0]), ('front', [sx*0.5, 0.3, -1])):
            ln = math.sqrt(H.dot(dv, dv))
            cams.append({'name': f'fist_{sd}_{name}', 'eye': [round(c[k]+dv[k]*4.0/ln, 3) for k in range(3)],
                         'target': [round(v, 3) for v in c]})
    # the wings and the halo where the rest pose puts them
    rest = world_frames({}, 0.0)
    _, wp = rest['wing_l']
    c = [0.0, wp[1]+0.4, wp[2]]
    for name, d in (('wing_back', [-0.55, 0.3, 0.8]), ('wing_side', [-1, 0.12, 0.05]),
                    ('wing_front', [-0.35, 0.2, -1])):
        ln = math.sqrt(H.dot(d, d))
        cams.append({'name': name, 'eye': [round(c[k]+d[k]*10.5/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    hr, hp = rest['head']
    c = H.add(hp, H.mv(hr, [0, HALO_CENTRE[1]+0.2, HALO_CENTRE[2]-0.3]))
    for name, d in (('halo_side', [-1, 0.1, 0]), ('halo_quarter', [-0.7, 0.35, -0.8])):
        ln = math.sqrt(H.dot(d, d))
        cams.append({'name': name, 'eye': [round(c[k]+d[k]*5.5/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    return cams


def flex_cameras(stance, drop):
    cams = [
        {'name': 'flex_side_right', 'eye': [-17.0, 6.0, -1.0], 'target': [0, 6.0, -1.0]},
        {'name': 'flex_side_left', 'eye': [17.0, 6.0, -1.0], 'target': [0, 6.0, -1.0]},
        {'name': 'flex_front_quarter', 'eye': [-12.0, 8.0, -14.0], 'target': [0, 6.0, -1.0]},
        {'name': 'flex_back_quarter', 'eye': [12.0, 11.0, 14.0], 'target': [0, 8.0, 0.0]},
    ]
    fr = world_frames(stance, drop)
    for jid, dv, dist in (('foot_r', [-1, 0.3, -0.2], 4.2), ('foot_l', [1, 0.3, 0.1], 4.2),
                          ('shin_r', [-1, 0.2, 0.3], 4.5), ('shin_l', [1, 0.2, -0.2], 4.5),
                          ('forearm_l', [1, 0.3, -0.3], 4.0), ('hand_r', [-1, 0.2, -0.4], 4.5),
                          ('hand_l', [0.8, 0.3, -0.8], 4.5), ('torso', [-1, 0.2, -0.6], 6.0),
                          ('upper_arm_r', [-1, 0.0, -0.3], 4.5), ('halo', [-1, 0.3, -0.4], 5.0)):
        _, p = fr[jid]
        ln = math.sqrt(H.dot(dv, dv))
        cams.append({'name': f'flex_{jid}', 'eye': [round(p[k]+dv[k]*dist/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in p]})
    return cams


# ---- writing ---------------------------------------------------------------------------------

# Pairs every move may pass into each other: Shadow's (the knuckle guard in the forearm's cuff
# when the wrist bends; the waist and chest with a raised thigh), each wing's hinge in the wing
# pack it is set into, and each wing with the helm and the halo: the parts check fits the wing's
# plates with one box (its 'folded' node, 7.4 m by 2.9 m), which reaches the neck and the ring
# behind the helm as soon as the wing lifts, while the plates themselves pass under the ring
# (checked on the moves' previews, the wings half open and spread).
ALLOW = [['forearm_r', 'weapon_r'], ['forearm_l', 'weapon_l']] + [
    [f'torso/{n}', f'thigh_{s}/{m}'] for s in 'rl' for n in ('waist', 'chest')
    for m in ('thigh', 'hip_drum')] + [['torso', 'wing_l'], ['torso', 'wing_r']] + [
    [p, f'wing_{s}'] for s in 'lr' for p in ('head', 'halo')]


def write_rig(stance, drop, part_recipes, height):
    parts = []
    for jid, parent, offset, rest, part, side in skeleton():
        pname = H.part_name('seraph', part, side)
        e = {'id': jid, 'parent': parent, 'offset': [round(c, 4) for c in offset]}
        if rest:
            e['rotate'] = rest
        e['recipe'] = f'parts/{pname}.asset.json'
        e['asset'] = f'ASSET_{pname.upper()}'
        e.update(H.part_facts(part_recipes[pname]))
        role, rng = RANGES['weapon' if part == 'knuckle' else part]
        e['role'] = role
        e['range'] = rng
        parts.append(e)
    mounts = [{'id': f'weapon_{s}', 'parent': f'hand_{s}', 'offset': [0, KNUCKLE, 0],
               'rotate': S.CLAW_REST, 'part': f'weapon_{s}',
               'note': "the knuckles (Shadow's claw mount); the knuckle guard's +Y runs out of "
                       "them (the hand's -Y)"}
              for s in 'rl']
    rig = {
        'format': 'mei-rig', 'version': 1, 'name': 'seraph',
        'units': 'metres; Y up; the mech faces -Z, +X is its left',
        'rotation': 'degrees, applied X then Y then Z, in the parent joint frame (the Asset Kit\'s '
                    'order). Not mirrored between sides: on a hanging limb +X swings it forward; '
                    '+Z swings a left limb out (+X) and a right limb in, so a mirrored pose negates '
                    'Y and Z',
        'root': 'pelvis',
        'root_note': "the root (fight origin) is on the floor under the pelvis; pelvis.offset is "
                     "the rest-pose hip-axle height, a pose lowers it by its 'drop'",
        'body': "Momentum Robotics' Seraph (MR-02): Shadow's skeleton and joint offsets, an "
                "armoured paladin's body on it (helm, breastplate, gauntlet fists with gold "
                "knuckle guards as the weapon parts), two folded wings on joints of their own "
                "(wing_l, wing_r) and a halo on its own joint (halo, the head's child)",
        'height': height,
        'parts': parts,
        'mounts': mounts,
        'fist': {
            'note': "The knuckle guards are weapon_r and weapon_l (one mesh) on Shadow's claw "
                    "mounts: keep the weapon joints at 0 (a fist does not open). The fist's "
                    "front is the knuckle guard's +Y end, about 0.14 m past the mount, 1.34 m "
                    "from the wrist",
            'front': [0.0, 0.14, 0.0],
        },
        'wings': {
            'note': 'wing_l and wing_r are folded at rotation 0. Spread is the left wing at '
                    'WING_SPREAD, the right mirrored (y and z negated); ward is the Wing Ward\'s '
                    'wrap, the plates round the sides to the front',
            'spread_l': list(WING_SPREAD),
            'spread_r': [WING_SPREAD[0], -WING_SPREAD[1], -WING_SPREAD[2]],
            'ward_l': list(WING_WARD),
            'ward_r': [WING_WARD[0], -WING_WARD[1], -WING_WARD[2]],
        },
        'halo': {
            'note': "the halo joint's pivot is 0.45 m above and 0.78 m behind the ring; 'raised' "
                    "lifts the ring 0.9 m straight up; 'centre' is the ring's centre in the halo "
                    "joint's frame (for the flare)",
            'raised': list(HALO_RAISED),
            'centre': [round(HALO_CENTRE[k]-HALO_PIVOT[k], 4) for k in range(3)],
        },
        'poses': {'guard': {'drop': round(drop, 4), 'rotate': dict(stance),
                            'note': "Seraph's boxer's guard: upright, the right foot and fist "
                                    'leading, the right fist at chin height about 3 m out, the '
                                    'left by the jaw, the elbows in, the knees soft, the wings '
                                    'folded, the halo down; every move starts and ends in it'},
                  'sink': {'drop': SINK_DROP, 'rotate': dict(SINK),
                           'note': "Shadow's sink, the fists closed"},
                  'spread': {'drop': round(drop, 4), 'rotate': spread(stance),
                             'note': 'the guard with both wings spread'}},
        'allow': ALLOW,
        'allow_note': "pairs of parts every move may pass into each other (a move's \"allow\" adds "
                      "more), or part/piece pairs: Shadow's, each wing's hinge drum set into the "
                      "wing pack, and each wing with the helm and the halo (the plates' one box "
                      "reaches them when a wing lifts; the plates pass under the ring)",
        'triangles': sum(p['triangles'] for p in parts),
    }
    H.write(HERE/'seraph.rig.json', rig)
    return rig


def height():
    """The rest pose's top (from the assembled recipe's bounds)."""
    return H.part_facts(recipe('h', assemble({}), 4000))['bounds']['max'][1]


def main():
    budget = 1900
    H.write(HERE/'seraph.asset.json', recipe('seraph', assemble(STANCE, DRAWN_DROP), budget))
    H.write(HERE/'seraph_rest.asset.json', recipe('seraph_rest', assemble({}), budget))
    written = {}
    for part in PARTS:
        for side in (('l', 'r') if part in SIDED else (None,)):
            pname = H.part_name('seraph', part, side)
            r = recipe(pname, geometry(part, side), 400, 512)
            H.write(HERE/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    for p in (HERE/'parts').glob('seraph_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    H.write(HERE/'seraph_flex.asset.json', recipe('seraph_flex', assemble(FLEX, FLEX_DROP), budget))
    H.write(HERE/'cameras.json', cameras(STANCE, DRAWN_DROP))
    H.write(HERE/'cameras_flex.json', flex_cameras(FLEX, FLEX_DROP))
    H.write(HERE/'asset-preview.json', LOOK)
    h = round(height(), 3)
    rig = write_rig(STANCE, DRAWN_DROP, written, h)
    print(f'seraph: {rig["triangles"]} triangles, {h} m tall')


if __name__ == '__main__':
    main()
