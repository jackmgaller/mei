#!/usr/bin/env python3
"""Mech Expo 2000: Momentum's angel (MR-02), concept A ("fists"), third look study.

Not packed and not in the roster: recipes for concept renders, for the owner to approve before
the real mech is built (they live outside models/, whose every recipe tools/gen_mechexpo_assets.py
packs). The story: Umbral made a dark copy of Momentum's Hero (the Double-blade Hero); Momentum
answers with a holy copy of Umbral's Shadow, an angel, an honest brawler on Momentum's kinetic
power. The owner chose concept A (armoured gauntlet fists) and asked for more love in the
colouring and the model. Round two was Shadow's thin frame repainted; this round keeps Shadow's
skeleton (the shared enum Part, Shadow's joint offsets: ../../models/shadow/make_shadow.py) so
Shadow's keyframes still play, and builds a body of its own on it:

  head       a knight's helm on a longer neck (it clears the pauldrons side-on): a white visor
             slit glowing in a dark face under a jutting brow, a chrome chin guard, a gold blade
             crest on the brow, a gold wing swept back from each temple, and the gold halo
             floating above and behind, tilted back
  torso      a broad breastplate (wider and deeper than Shadow's chest) over a narrow gunmetal
             waist, a red kinetic core in a gold setting on the sternum, a chrome collar, and on
             the back a wing pack carrying the two folded wings: each three layered plates (the
             upper wing with its arch over the shoulder, two long flight plates under it) whose
             clean pointed tips step down behind the thighs, where Shadow's cape plates hung
  pauldron   a big rounded two-tier shoulder shell, Momentum's mark on its flat outer panel
  upper_arm  the gunmetal frame (the dark between the shoulder and the bracer)
  forearm    a heavy bracer flaring to a wide cuff, an elbow guard behind
  hand       the gauntlet fist, as long as Shadow's hand (wrist to knuckles 1.2 m), so Shadow's
             arm keys reach the same places
  weapon     the knuckle guard: a gold band round the fist's end, ridged over the knuckles, on
             Shadow's claw mount (the trails follow it)
  pelvis     a red codpiece, front plates (faulds) and side skirts over the gunmetal hips
  thigh, shin, foot   heavier legs: a plated thigh (MR-02 plate outside), a pointed knee guard,
             a flared greave and the ankle skirt, a pointed sabaton

The paint is in roles (the material names), and a scheme gives each role its colour, so the
same model is drawn in each scheme tried: SCHEMES, below. The chosen one paints the poses.
1,892 triangles (Shadow 1,800, the Hero 1,776), the same in every pose.

Writes, beside this script: angel_a3_{idle,attack,judgement}.asset.json (the poses, in the
chosen scheme), angel_a3_paint_{1,2,3}.asset.json (the idle in each scheme), angel_a3_rest
(every joint at 0), cameras.json and asset-preview.json (the hangar look, as Shadow's).
render_angel_a3.py renders them beside Shadow and the Hero and draws the sheets.
Run from anywhere: python3 carts/mechexpo/concepts/angel_a/make_angel_a3.py (standard library
only).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parents[1]/'models'
sys.path.insert(0, str(MODELS/'shadow'))
sys.path.insert(0, str(MODELS/'hero'))
import make_hero as H  # noqa: E402
import make_shadow as S  # noqa: E402
import mxpaint as P  # noqa: E402

T, loft, crect, by_side, cyl_x, box = H.T, H.loft, H.crect, H.by_side, H.cyl_x, H.box
plate_yz = S.plate_yz

# ---- paint ------------------------------------------------------------------------------------
# The base colours: Momentum's red and white flipped (white body, red accents), chrome trim, gold
# for the holy parts, and a dark gunmetal frame so the white has something to stand against.

BASE = {
    'white':  '#ffffff',
    'red':    '#e01e26',
    'chrome': '#c6d0dc',
    'gold':   '#e8b030',
    'frame':  '#3a4150',
    'dark':   '#1c2029',
    'navy':   '#2c3a5e',
}
SMOOTH = {'chrome', 'gold'}

# The roles: what each surface is. A scheme maps every role to a base colour.
ROLES = ['armour', 'helm', 'chest', 'yoke', 'core', 'core_rim', 'collar', 'waist', 'pack',
         'pauldron', 'pauldron_rim', 'bicep', 'bracer', 'cuff', 'elbow', 'fist', 'knuckles',
         'codpiece', 'skirt', 'skirt_edge', 'thigh', 'knee', 'shin', 'shin_front', 'ankle',
         'foot', 'toe', 'covert', 'covert_edge', 'flight', 'flight_edge', 'lining', 'crest',
         'temple', 'chin', 'frame', 'joint', 'dark']

# Scheme 1, "gauntlets": red in three kinds of place: what strikes (forearm cuffs and fists), the
# armour's edges (the pauldrons' lower tier, the knee guards, the codpiece) and each wing's arch;
# the rest white on a dark gunmetal frame, the flight plates chrome; gold only for the holy parts
# (the halo, the crest and temple wings, the core's setting, the knuckles).
SCHEME_1 = {
    'armour': 'white', 'helm': 'white', 'chest': 'white', 'yoke': 'white', 'core': 'red',
    'core_rim': 'gold', 'collar': 'chrome', 'waist': 'frame', 'pack': 'frame',
    'pauldron': 'white', 'pauldron_rim': 'red', 'bicep': 'frame', 'bracer': 'white',
    'cuff': 'red', 'elbow': 'chrome', 'fist': 'red', 'knuckles': 'gold',
    'codpiece': 'red', 'skirt': 'white', 'skirt_edge': 'white', 'thigh': 'white', 'knee': 'red',
    'shin': 'white', 'shin_front': 'white', 'ankle': 'frame', 'foot': 'white', 'toe': 'white',
    'covert': 'white', 'covert_edge': 'red', 'flight': 'chrome', 'flight_edge': 'chrome',
    'lining': 'frame', 'crest': 'gold', 'temple': 'gold', 'chin': 'chrome', 'frame': 'frame',
    'joint': 'chrome', 'dark': 'dark',
}
# Scheme 2, "Hero flipped": the Hero's own blocking with red and white swapped: red pauldron
# shells over white, red chest corners and forearm panels, red knee guards and shin fronts, red
# sabatons; white fists with gold knuckles.
SCHEME_2 = {
    **SCHEME_1,
    'yoke': 'red', 'pauldron': 'red', 'pauldron_rim': 'chrome', 'cuff': 'chrome',
    'fist': 'white', 'bracer': 'white', 'codpiece': 'white', 'skirt': 'chrome',
    'skirt_edge': 'red', 'shin_front': 'red', 'foot': 'red', 'toe': 'white', 'ankle': 'frame',
    'covert': 'white', 'covert_edge': 'white', 'flight_edge': 'chrome', 'chest': 'white',
}
# Scheme 3, "royal": white plates on a deep navy frame (darker values, more form), red kept to
# a few big shapes (the upper wing, the breastplate's yoke, the knee guards), gold fists.
SCHEME_3 = {
    **SCHEME_1,
    'frame': 'navy', 'waist': 'navy', 'pack': 'navy', 'bicep': 'navy', 'lining': 'navy',
    'ankle': 'navy', 'yoke': 'red', 'cuff': 'gold', 'fist': 'white', 'knuckles': 'gold',
    'codpiece': 'white', 'covert': 'red', 'covert_edge': 'white', 'knee': 'red',
    'skirt_edge': 'red',
}
SCHEMES = {'1': ('Gauntlets', SCHEME_1), '2': ('Hero flipped', SCHEME_2), '3': ('Royal', SCHEME_3)}
CHOSEN = '1'

GLOW, HALO = '#f4fbff', '#ffd659'
SERIAL_FIELD, SERIAL_INK = '#e4e7ec', BASE['dark']


def materials(scheme):
    m = {}
    for role in ROLES:
        c = scheme[role]
        m[role] = {'color': BASE[c]}
        if c in SMOOTH:
            m[role]['smooth'] = True
    m['glow'] = {'color': GLOW, 'class': 'emissive'}
    m['halo'] = {'color': HALO, 'class': 'emissive'}
    pf = BASE[scheme['pauldron']]
    red = BASE['red'] if scheme['pauldron'] != 'red' else BASE['white']
    white = BASE['white'] if scheme['pauldron'] != 'red' else BASE['red']
    m['emblem'] = {'color': pf, 'texture': {
        **H.emblem_texture(P.emblem_momentum(red=red, white=white), pf), 'projection': 'fit'}}
    m['serial'] = {'color': SERIAL_FIELD, 'texture': {
        **P.serial_plate('MR-02', SERIAL_FIELD, SERIAL_INK), 'projection': 'fit'}}
    m['hazard'] = {'color': BASE['red'], 'texture': {
        **P.hazard([BASE['red'], BASE[scheme['ankle']]]), 'projection': 'box',
        'scale': [0.32, 0.32]}}
    return m


# White comes out grey under the cart's ambient (0.66) on the flanks the side camera sees;
# round two found 0.8 reads white against the hangar. The direction is the cart's.
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.8}
LOOK = {'background': ['#56647a', '#a4b0be'], 'ground': '#7a8592'}

# ---- the skeleton: Shadow's ---------------------------------------------------------------------

KNUCKLE = S.KNUCKLE          # wrist to the knuckles (the weapon mount): -1.2
SHOULDER, NECK, UPPER, FORE = S.SHOULDER, S.NECK, S.UPPER, S.FORE

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
    # the codpiece: a pointed shield on the front of the hips
    cod = loft('codpiece', 'z', [
        (-0.74, [(0.0, -0.95), (0.3, -0.45), (0.34, 0.42), (-0.34, 0.42), (-0.3, -0.45)]),
        (-0.52, [(0.0, -1.05), (0.4, -0.5), (0.44, 0.5), (-0.44, 0.5), (-0.4, -0.5)]),
    ], lambda k, j: 'codpiece', 'codpiece', 'frame')
    # the faulds: a plate a side over the front of each thigh, hanging from the belt, tilted out
    fauld = group('faulds', [group('fauld', [
        plate_yz('fauld_plate', [(-0.42, 0.0), (0.38, 0.0), (0.3, -1.05), (-0.25, -1.25)], 0.1,
                 'skirt', 'frame', 'skirt_edge', [0, 0, 0])],
        [0.66, 0.42, -0.52], [0, 62, 12])], scale=None)
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
    """A broad breastplate over a narrow waist; the red core on the sternum; the wing pack and
    the folded wings on the back."""
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
    # the core: a red hexagon in a gold setting, standing proud of the sternum
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
    return [waist, chest, setting, gem, collar, pack] + wings()


# ---- the folded wings ---------------------------------------------------------------------------
# Each wing is three plates in its own Y-Z plane (outlines as (z, y), +z back, from the root high
# on the back): the upper wing (the covert) with its arch rising over the shoulder, and two long
# flight plates under it, each reaching further down and back to a clean point. Layered outward
# (the covert outermost), so from the side the three tips step down behind the thigh and from
# the front the arches show over the shoulders.

COVERT = [(-0.25, -0.2), (-0.3, 0.75), (0.0, 1.45), (0.5, 1.85), (0.95, 1.7), (1.25, 1.0),
          (1.35, -0.6), (1.2, -1.9), (0.95, -2.6), (0.45, -1.3)]
# the arch's band: the covert's leading edge over the top, a narrow plate on its outer face
COVERT_BAND = [(-0.24, 0.4), (0.0, 1.36), (0.5, 1.76), (0.92, 1.62), (1.18, 0.98), (0.98, 0.96),
               (0.8, 1.4), (0.48, 1.5), (0.12, 1.1), (-0.02, 0.4)]
FLIGHT_A = [(0.1, 0.3), (0.85, 0.95), (1.4, 0.4), (1.6, -1.2), (1.55, -3.0), (1.3, -3.9),
            (0.9, -1.6)]
FLIGHT_B = [(0.3, -0.2), (1.1, 0.2), (1.62, -0.9), (1.8, -2.8), (1.68, -4.4), (1.42, -5.2),
            (1.0, -2.6)]
WING_ROOT = (0.82, 2.72, 0.95)
WING_TURN = [5, -10, -7]       # the left wing's: trailing edge in toward the spine, top out


def wing():
    """The left wing, in its own frame."""
    return [
        plate_yz('covert', COVERT, 0.08, 'covert', 'lining', 'covert_edge', [0.14, 0, 0]),
        plate_yz('covert_band', COVERT_BAND, 0.05, 'covert_edge', 'covert_edge', 'covert_edge',
                 [0.215, 0, 0]),
        plate_yz('flight_a', FLIGHT_A, 0.08, 'flight', 'lining', 'flight_edge', [0.02, 0, 0]),
        plate_yz('flight_b', FLIGHT_B, 0.08, 'flight', 'lining', 'flight_edge', [-0.1, 0, 0]),
    ]


def wings():
    left = group('wing_l', wing(), list(WING_ROOT), WING_TURN)
    right = group('wing_r', [group('wing_r_inner', wing(), list(WING_ROOT), WING_TURN)],
                  scale=[-1, 1, 1])
    return [left, right]


def halo(r=0.72, tube=0.1, seg=10):
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


HALO_AT, HALO_TILT = [0, 2.42, 0.34], [-30, 0, 0]
HELM_LIFT = 0.16


def head():
    """A knight's helm: white, a dark face band with the white visor slit standing proud of it
    under a jutting brow, a pointed chin guard, a gold blade crest on the brow, a small swept-back
    wing at each temple; the halo above and behind."""
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
    ring = group('halo', [halo()], HALO_AT, HALO_TILT)
    # the helm stands on a longer neck than Shadow's hood, so it clears the pauldrons side-on
    return [neck, group('helm_raised', [helm, visor, brow, chin, crest, temple, ring],
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
    # the lower tier: a flared rim plate under the shell, over the top of the upper arm
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
    # the curled fingers on the palm side, the thumb across them at the front
    fingers = box('fingers', [0.3, 0.72, 0.96], 'frame', [-0.26, -0.84, 0.0])
    thumb = box('thumb', [0.38, 0.32, 0.3], 'fist', [-0.12, -0.7, -0.56])
    return [wrist, fist, fingers, thumb]


def knuckle_guard():
    """The weapon part (Shadow's claw mount, at the knuckles): a gold band round the fist's end
    and four knuckle studs along it. Claw frame: +Y out of the knuckles, the hand's +Z is -Z."""
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
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': hand, 'claw': knuckle_guard,
    'thigh': thigh, 'shin': shin, 'foot': foot,
}


def assemble(stance, drop, dz=0.0):
    """Shadow's rig as nested groups (make_shadow.assemble) with these parts; `dz` moves the
    pelvis back (+Z), as an Animation Kit offset does."""
    sk = S.skeleton()
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
                 'children': H.geometry(part, side, PARTS) + [node(k) for k in kids.get(jid, [])],
                 'transform': T(None, stance.get(jid))}
        if rest:
            return {'id': f'{jid}_mount', 'op': 'group', 'children': [inner],
                    'transform': T([round(c, 4) for c in t], rest)}
        inner['transform'] = T([round(c, 4) for c in t], stance.get(jid))
        return inner
    return [node('pelvis')]


def recipe(name, nodes, scheme, budget=1900):
    mats = materials(scheme)
    r = H.recipe(name, nodes, budget, 2048, materials=mats)
    r['materials'] = {k: v for k, v in mats.items() if k in H.used(nodes)}
    r['lighting'] = LIGHTING
    return r


# ---- posing -----------------------------------------------------------------------------------

def mirror(r):
    return [r[0], -r[1], -r[2]]


def solve_arm(side, point, local=(0.0, 0.0, 0.0), aligns=(), start=None, elbow_out=1.2):
    """Shoulder, elbow and wrist angles (in the torso's frame) that put the hand's `local` point
    at `point` and turn each hand vector of `aligns` [(local, wanted), ...] toward its wanted
    direction, within Shadow's joint ranges. A right arm is solved as the left one mirrored."""
    def mir(v):
        return [-v[0], v[1], v[2]]
    if side == 'r':
        point = mir(point)
        aligns = [(mir(a), mir(b)) for a, b in aligns]
    sh = list(SHOULDER)
    lim = [(-70, 200), (-45, 45), (-110, 25), (0, 150), (-40, 40), (-80, 80), (-90, 90), (-40, 40)]

    def cost(p):
        ru = H.rot(p[0:3])
        elbow = H.add(sh, H.mv(ru, [0, -UPPER, 0]))
        rf = H.mm(ru, H.rot([p[3], p[4], 0]))
        wrist = H.add(elbow, H.mv(rf, [0, -FORE, 0]))
        rh = H.mm(rf, H.rot(p[5:8]))
        q = H.add(wrist, H.mv(rh, list(local)))
        e = sum((q[k]-point[k])**2 for k in range(3))*8
        for v, w in aligns:
            hv = H.mv(rh, list(v))
            ln = math.sqrt(H.dot(w, w))
            e += sum((hv[k]-w[k]/ln)**2 for k in range(3))*2
        e += max(0.0, elbow_out-elbow[0])**2*20
        e += sum(c*c for c in p[5:8])*1e-5
        return e
    p = list(start or [20.0, 0.0, -10.0, 90.0, 0.0, 0.0, 0.0, 0.0])
    step = 16.0
    while step > 0.05:
        moved = True
        while moved:
            moved = False
            for i in range(len(p)):
                for d in (step, -step):
                    q = list(p)
                    q[i] = min(max(q[i]+d, lim[i][0]), lim[i][1])
                    if cost(q) < cost(p)-1e-12:
                        p, moved = q, True
        step /= 2
    out = {'upper_arm': [round(c, 1) for c in p[0:3]],
           'forearm': [round(p[3], 1), round(p[4], 1), 0], 'hand': [round(c, 1) for c in p[5:8]]}
    if side == 'r':
        out = {k: mirror(v) for k, v in out.items()}
    return {f'{k}_{side}': v for k, v in out.items()}


FIST = (0.0, -0.75, 0.0)          # the middle of the fist, in the hand's frame

# Shadow's frames, read with `python3 tools/mei_anim.py pose carts/mechexpo/anims/shadow/MOVE
# .anim.json --frames N --json` (the offset is forward, up; forward is -Z here).
# atk_f (Lunging Claw) frame 13, the contact pose: offset (-1.03, -1.76)
LUNGE = {
    'pelvis': [0, -8, 0], 'torso': [-22.6, -16, 0], 'head': [26, 10, 0],
    'thigh_r': [34, 0, -11], 'shin_r': [-69.7, 0, 0], 'foot_r': [35.7, 0, 11],
    'thigh_l': [-12, 0, 12], 'shin_l': [-36.1, 0, 0], 'foot_l': [48.1, 0, -12],
    'upper_arm_r': [105.6, 0, 30], 'forearm_r': [0, 0, 0], 'hand_r': [11.1, 1.3, -12.3],
    'weapon_r': [0, 0, 0], 'pauldron_r': [30, 0, -10],
    'upper_arm_l': [-30, 0, 18], 'forearm_l': [30, 0, -10], 'hand_l': [40, 0, 0],
    'weapon_l': [6, 0, 0], 'pauldron_l': [12.6, 0, 15],
}
LUNGE_DROP, LUNGE_DZ = 1.7556, 1.0278


def with_pauldrons(st):
    """Shadow's rule: the pauldron follows the upper arm part way (0.35 of x, 0.5 of z)."""
    st = dict(st)
    for s in 'rl':
        ua = st.get(f'upper_arm_{s}', [0, 0, 0])
        st[f'pauldron_{s}'] = [round(ua[0]*0.35, 2), 0, round(ua[2]*0.5, 2)]
    return st


def poses():
    """{name: (stance, drop, dz)}."""
    out = {}
    # Idle: an upright boxer's guard, distinct from Shadow's low mantis crouch. Turned side-on,
    # weight on bent knees, the body upright, the chin down; the lead (right) fist up at eye
    # height in front, the rear fist by the chin, both elbows down and in.
    drop = 0.8
    st = {'pelvis': [0, -14, 0], 'torso': [-6, -12, 0], 'head': [10, 16, 0],
          'thigh_r': [24, 0, -9], 'thigh_l': [-18, 0, 9]}
    st.update(solve_arm('r', [-0.55, 3.1, -2.75], FIST, [((0, -1, 0), [0, 0.75, -0.66])]))
    st.update(solve_arm('l', [0.75, 2.9, -2.15], FIST, [((0, -1, 0), [0, 0.9, -0.45])],
                        elbow_out=1.35))
    st.update({'weapon_r': [0, 0, 0], 'weapon_l': [0, 0, 0]})
    out['idle'] = (with_pauldrons(S.pose(st, drop)), drop, 0.0)

    # Attack: Lunging Claw's contact frame (its body and both arms as they are: the right arm
    # and fist in one straight line at full reach, the left fist drawn back by the hip), a
    # lunging straight. The hand is straightened (Shadow's wrist aims the claw), the claws' keys
    # zeroed, and the stride lengthened with the knees solved so both soles stay on the floor.
    st = {k: v for k, v in LUNGE.items() if k not in ('shin_r', 'shin_l', 'foot_r', 'foot_l')}
    st.update({'hand_r': [0, 0, 0], 'weapon_r': [0, 0, 0], 'weapon_l': [0, 0, 0],
               'hand_l': [20, 0, 0], 'thigh_r': [46, 0, -11], 'thigh_l': [-24, 0, 12]})
    st = {**S.pose(st, LUNGE_DROP), 'pauldron_r': LUNGE['pauldron_r'],
          'pauldron_l': LUNGE['pauldron_l']}
    out['attack'] = (st, LUNGE_DROP-0.03, LUNGE_DZ)    # drawn 3 cm up: the pitched toe

    # Judgement: standing tall, planted wide, the right fist thrust straight up to call the
    # light down, the left chambered at the hip, the head lifted to the fist.
    drop = 0.55
    st = {'pelvis': [0, -6, 0], 'thigh_r': [22, 0, -10], 'thigh_l': [-12, 0, 11],
          'torso': [2, -8, 0], 'head': [-20, 6, 0],
          'upper_arm_r': [178, 0, 10], 'forearm_r': [4, 0, 0], 'hand_r': [0, 0, 0]}
    st.update(solve_arm('l', [1.05, 1.35, -0.35], FIST, [((0, -1, 0), [0, 0.15, -1])]))
    st.update({'weapon_r': [0, 0, 0], 'weapon_l': [0, 0, 0]})
    out['judgement'] = (with_pauldrons(S.pose(st, drop)), drop, 0.0)
    return out


# ---- cameras ----------------------------------------------------------------------------------

def cameras():
    """The fight's side view at game distance (31.2 m: the mech about 80 px of 240), a nearer side
    view, three-quarters from the front and the back, and the halves of fight frames: this mech
    7 m left of centre facing right, the other 7 m right facing left; and closer (22 m, the
    camera zoomed in as the mechs meet, about 115 px), 5.5 m either side. Last, the helm close up
    where the rest pose puts it (nothing in front of it there), from the side and a quarter."""
    hr, hp = S.world_frames({}, 0.0)['head']
    hc = H.add(hp, H.mv(hr, [0, 0.95+HELM_LIFT, -0.2]))
    heads = []
    for name, dv in (('head_side', [-1, 0.15, 0]), ('head_quarter', [-0.75, 0.3, -0.8])):
        v = H.mv(hr, dv)
        ln = math.sqrt(H.dot(v, v))
        heads.append({'name': name, 'eye': [round(hc[k]+v[k]*4.6/ln, 3) for k in range(3)],
                      'target': [round(c, 3) for c in hc]})
    return heads + [
        {'name': 'side', 'eye': [-31.2, 5.8, -2.0], 'target': [0, 5.8, -2.0]},
        {'name': 'side_near', 'eye': [-21.0, 8.2, -1.5], 'target': [0, 8.2, -1.5]},
        {'name': 'three_quarter', 'eye': [-13.0, 10.5, -16.5], 'target': [0, 8.2, -1.0]},
        {'name': 'back_quarter', 'eye': [12.5, 11.0, 15.5], 'target': [0, 8.2, 0.5]},
        {'name': 'front', 'eye': [0, 9.0, -21.0], 'target': [0, 8.2, 0]},
        {'name': 'fight_left', 'eye': [-31.2, 5.8, -7.0], 'target': [0, 5.8, -7.0]},
        {'name': 'fight_right', 'eye': [31.2, 5.8, -7.0], 'target': [0, 5.8, -7.0]},
        {'name': 'close_left', 'eye': [-22.0, 6.4, -5.5], 'target': [0, 6.4, -5.5]},
        {'name': 'close_right', 'eye': [22.0, 6.4, -5.5], 'target': [0, 6.4, -5.5]},
    ]


def main():
    chosen = SCHEMES[CHOSEN][1]
    ps = poses()
    for name, (st, drop, dz) in ps.items():
        H.write(HERE/f'angel_a3_{name}.asset.json',
                recipe(f'angel_a3_{name}', assemble(st, drop, dz), chosen))
        if name == 'idle':
            for k, (_, scheme) in SCHEMES.items():
                H.write(HERE/f'angel_a3_paint_{k}.asset.json',
                        recipe(f'angel_a3_paint_{k}', assemble(st, drop, dz), scheme))
    H.write(HERE/'angel_a3_rest.asset.json', recipe('angel_a3_rest', assemble({}, 0.0), chosen))
    H.write(HERE/'cameras.json', cameras())
    H.write(HERE/'asset-preview.json', LOOK)


if __name__ == '__main__':
    main()
