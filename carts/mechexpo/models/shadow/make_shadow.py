#!/usr/bin/env python3
"""Mech Expo 2000: Shadow (Umbral Research), the trickster: UR-01.

Umbral Research is secretive and experimental: black and violet, antimatter. Shadow is its base
mech, and it must read apart at a glance from the Double-blade Hero (Umbral's echo of the Hero,
also black and violet): tall and thin, a cape, one eye, claws, no blades. Its claws are the
owner's ask: long thin arms ending in hands as big as the forearms, each with four long talons
glowing violet at the tips, fanned in the plane the side camera sees so they read at 80 px.

It is built on the cart's one skeleton (anim.akr's enum Part: the Hero's ids, order and
parents) with its own joint offsets, so the Animation Kit and the runtime need nothing new:

  pelvis        narrow hips; the hip axle
  torso         a tall, slim chest and a long segmented waist; a high collar behind the head;
                three rigid cape plates hanging from the upper back (a back plate and two that
                wrap the flanks), so the cape turns with the torso
  head          a hood with a peak, a dark mask and one round violet eye that stands proud of
                the face, so it shows from the side
  pauldron_*    a narrow shoulder plate rising to a spike, Umbral's mark on its outside, and a
                cape plate hanging from it outside the upper arm (it turns with the pauldron,
                which follows the upper arm part way)
  upper_arm_*   long and thin
  forearm_*     long, flaring to a wide cuff at the wrist, an elbow spike behind
  hand_*        the big hand: a palm as long as the forearm's cuff is wide, broad fore and aft
                (the side camera sees it whole), an armoured back with knuckle spikes
  weapon_*      the claw: four talons on the knuckles (three fingers fanned fore and aft, a
                thumb opposing them), hooked downward when the arm reaches forward, glowing at the tips. The
                claw is the weapon part, on a mount at the knuckles, so the effects' trails
                follow it and the animators can open and close it at the weapon joint
  thigh_*, shin_*, foot_*   long thin legs, spiked knees, pointed feet with a heel talon

The trade-show finish is Umbral's: its eclipse on the pauldrons, a serial plate on each thigh
(UR-01) and violet-and-black hazard stripes round the ankles.

Writes, beside this script: shadow.asset.json (assembled, in its guard), shadow_rest.asset.json
(the rest pose), shadow_flex.asset.json (every joint bent far, for checking; not packed),
parts/shadow_*.asset.json (each part alone, its origin at its joint), shadow.rig.json,
cameras.json, cameras_flex.json and asset-preview.json (the preview's hangar look). Helpers (the
loft builder, the writers) come from ../hero/make_hero.py; Umbral's mark from mxpaint.py.
Run from anywhere: python3 carts/mechexpo/models/shadow/make_shadow.py (standard library only).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'hero'))
import make_hero as H  # noqa: E402
import mxpaint as P  # noqa: E402

loft, crect, by_side, cyl_x, box, T = H.loft, H.crect, H.by_side, H.cyl_x, H.box, H.T

# ---- paint (STYLE.md: Umbral Research is black and violet; a neutral metal; one glow) --------
# Apart from the Double-blade Hero's: no light graphite plates. Shadow is black with deep violet
# cape plates lined in bright violet, gunmetal joints and talons, and the one glow (the eye and
# the talons' tips).

BLACK, CAPE, VIOLET = '#211e29', '#4a2a78', '#9a52f5'
GUN, DARK = '#6b6878', '#121016'

MATERIALS = {
    'black':  {'color': BLACK},                  # the body's plates
    'cape':   {'color': CAPE},                   # the cape plates' outsides, the hood's peak
    'violet': {'color': VIOLET},                 # the cape's lining, trim and edging
    'gun':    {'color': GUN, 'smooth': True},    # the neutral metal: joints, the talons' roots
    'frame':  {'color': '#3a3744'},              # darker joints and frame
    'dark':   {'color': DARK},                   # the mask, soles
    'talon':  {'color': '#b9a6e6', 'smooth': True},   # the talons: pale violet metal
    'vglow':  {'color': '#c77bff', 'class': 'emissive'},  # the eye and the talons' tips
    'emblem': {'color': BLACK, 'texture': {
        **P.texels(P.scaled(P.emblem_umbral(violet=VIOLET, black=BLACK), 28/56, 28/32, 14/56,
                            2/32), 56, 32, BLACK), 'projection': 'fit'}},
    'serial': {'color': '#5a5468', 'texture': {**P.serial_plate('UR-01', '#5a5468', DARK),
                                               'projection': 'fit'}},
    'hazard': {'color': VIOLET, 'texture': {**P.hazard([VIOLET, DARK]),
                                            'projection': 'box', 'scale': [0.32, 0.32]}},
}
LOOK = {'background': ['#56647a', '#a4b0be'], 'ground': '#7a8592'}

# ---- the rig: Shadow's joints (rest pose, in the parent's frame) -----------------------------
# Taller and thinner than the Hero: longer legs and arms, a narrower frame, a small head.

ANKLE, SHIN, THIGH = 0.8, 2.85, 2.85
HIP_X = 0.8
WAIST = 0.75
SHOULDER = (1.7, 2.85, 0.1)
NECK = (0.0, 3.3, -0.12)
UPPER, FORE = 2.55, 2.45
KNUCKLE = -1.2          # wrist to the knuckles: the claw's mount
CLAW_REST = [180, 0, 0]  # the claw's +Y along the hand's -Y (out of the knuckles), its -Z the
                         # hand's +Z: the talons hook toward the claw's -Z, which is down when
                         # the arm reaches forward
HIP_Y = ANKLE+SHIN+THIGH

# What each part is and how far its joint should turn (degrees, the kit's X, Y, Z; the rig's
# sense). Written into the rig for the animators.
RANGES = {
    'pelvis':    ('the narrow hips; the hip axle', 'x -20..20, y -40..40, z -10..10'),
    'torso':     ('the tall chest and long waist, the high collar, and the three cape plates on '
                  'its back (they turn with it: lean forward and the cape swings back)',
                  'x -45..30, y -60..60, z -20..20'),
    'head':      ('the hooded head, the one eye', 'x -30..35, y -60..60, z -15..15'),
    'pauldron':  ('the spiked shoulder plate and the cape plate hanging outside the upper arm; '
                  'follows the upper arm part way', "about 0.35 of the upper arm's x and 0.5 "
                  "of its z (more z and the cape plate opens like a wing)"),
    'upper_arm': ('the long thin upper arm', 'x -70..190, y -45..45, z: out -110..in 25 (sign by side)'),
    'forearm':   ('the long forearm, the wide cuff and the elbow spike', 'x 0..150 (forward only: '
                  'the elbow), y -40..40'),
    'hand':      ('the big hand: palm broad fore and aft, armoured back; the claw mounts at its '
                  'knuckles', 'x -80..80, y -90..90 (twist the claw to face the camera), z -40..40'),
    'weapon':    ('the claw: four talons on the knuckles, fanned in its Y-Z plane and hooked '
                  'toward its -Z (down when the arm reaches forward); its +Y runs from the '
                  'knuckles along the middle talon',
                  'x -40..30 (-x swings the talons toward their hooks: a closing grab; +x opens '
                  'them back), y and z -15..15'),
    'thigh':     ('the long thin thigh, the serial plate', 'x -60..110, z -40..30'),
    'shin':      ('the long shin, the spiked knee, the hazard skirt round the ankle',
                  'x -150..0 (back only: the knee)'),
    'foot':      ('the pointed foot, a heel talon', 'x -45..45, z -15..15'),
}

# ---- the parts (left / centre, origin at the joint) -----------------------------------------


def plate_yz(id_, pts, depth, out_mat, in_mat, edge, at, rotate=None):
    """A plate in the Y-Z plane (seen whole from the side), pts as (z, y), `depth` thick in X,
    its outside (+X, `out_mat`) and inside (`in_mat`), translated to `at` after `rotate`."""
    r = [0, 90, 0] if rotate is None else [rotate[0], 90+rotate[1], rotate[2]]
    return {'id': id_, 'op': 'extrude', 'depth': depth, 'material': out_mat,
            'faces': {'front': out_mat, 'back': in_mat, 'side': edge},
            'points': [[-z, y] for z, y in pts], 'transform': T(at, r)}


def plate_xy(id_, pts, depth, out_mat, in_mat, edge, at, rotate=None):
    """A plate in the X-Y plane (facing back), pts as (x, y); its back (+Z) `out_mat`."""
    return {'id': id_, 'op': 'extrude', 'depth': depth, 'material': out_mat,
            'faces': {'front': out_mat, 'back': in_mat, 'side': edge},
            'points': [list(p) for p in pts], 'transform': T(at, rotate)}


def pelvis():
    core = loft('core', 'y', [
        (0.5, crect(0.58, 0.48, 0.18)),
        (0.0, crect(0.7, 0.54, 0.22, 0.18)),
        (-0.45, crect(0.42, 0.44, 0.14, oz=-0.04)),
        (-0.78, crect(0.2, 0.3, 0.08, oz=-0.04)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'frame', 'f': 'black', 'fr': 'black', 'fl': 'black'},
                2: {'*': 'frame'}}),
        'frame', 'frame')
    axle = cyl_x('hip_axle', 0.3, 2*HIP_X+0.2, 6, 'gun', [0, 0, 0])
    return [core, axle]


CAPE_TOP = 3.05          # where the cape hangs from, on the torso
CAPE_SHAPE = [(-0.62, 0.0), (0.62, 0.0), (0.78, -4.9), (0.0, -5.75), (-0.78, -4.9)]


def torso():
    """The tall slim chest on a long waist, a high collar behind the head, the cape on the back."""
    waist = loft('waist', 'y', [
        (-0.32, crect(0.4, 0.36, 0.12)),
        (0.45, crect(0.44, 0.4, 0.13)),
        (1.05, crect(0.52, 0.46, 0.16)),
    ], by_side({0: {'*': 'frame'}, 1: {'*': 'gun'}}), 'frame', None)
    chest = loft('chest', 'y', [
        (0.9, crect(0.66, 0.52, 0.2, 0.16)),
        (1.85, crect(1.08, 0.7, 0.3, 0.2, oz=-0.05)),
        (2.6, crect(1.24, 0.76, 0.34, 0.22, oz=-0.06)),
        (3.1, crect(1.08, 0.68, 0.3, 0.2, oz=-0.02)),
        (3.4, crect(0.56, 0.46, 0.16, 0.14)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'r': 'cape', 'l': 'cape'},
                2: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                3: {'*': 'frame'}}),
        'frame', 'frame')
    sockets = cyl_x('shoulder_sockets', 0.34, 2*SHOULDER[0]-0.5, 6, 'frame',
                    [0, SHOULDER[1], SHOULDER[2]])
    # the high collar: a plate behind the neck rising to the head's crown, two more angled
    # forward at its sides, flaring out; behind the head, so the eye still shows side-on
    col = [(-0.5, 0.0), (0.5, 0.0), (0.7, 1.35), (0.0, 1.6), (-0.7, 1.35)]
    collar = {'id': 'collar', 'op': 'group', 'children': [
        plate_xy('collar_back', col, 0.12, 'black', 'violet', 'violet', [0, 3.2, 0.72], [-16, 0, 0])]}
    wings = {'id': 'collar_wings', 'op': 'group', 'children': [
        plate_xy('collar_wing', [(-0.3, 0.0), (0.32, 0.0), (0.36, 1.05), (-0.2, 1.25)], 0.1,
                 'black', 'violet', 'violet', [0.62, 3.2, 0.5], [-12, 52, -10])],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    # the cape: rigid plates from the upper back, deep violet outside, lined in bright violet,
    # tilted back so the hem clears the legs; the side plates wrap round the flanks, so the
    # side camera sees the cape as a shape, not an edge
    back = plate_xy('cape_back', CAPE_SHAPE, 0.12, 'cape', 'violet', 'violet',
                    [0, CAPE_TOP, 0.9], [-9, 0, 0])
    side = [(-0.55, 0.0), (0.55, 0.0), (0.62, -4.3), (0.0, -5.0), (-0.62, -4.3)]
    flanks = {'id': 'cape_flanks', 'op': 'group', 'children': [
        plate_xy('cape_flank', side, 0.1, 'cape', 'violet', 'violet',
                 [0.95, CAPE_TOP-0.1, 0.5], [-7, 58, 3])],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    return [waist, chest, sockets, collar, wings, back, flanks]


EYE = (0.0, 0.7, -0.77)    # the eye's front face, in the head's frame


def head():
    """A hood with a forward peak over a dark mask; one round violet eye standing proud of it."""
    neck = {'id': 'neck', 'op': 'cylinder', 'radius': 0.28, 'height': 0.6, 'segments': 4,
            'material': 'frame', 'transform': T([0, 0.2, 0], [0, 45, 0])}
    hood = loft('hood', 'y', [
        (0.2, crect(0.34, 0.4, 0.12, 0.1, oz=0.02)),
        (0.55, crect(0.44, 0.5, 0.16, 0.14)),
        (1.0, crect(0.42, 0.54, 0.16, 0.16, oz=0.04)),
        (1.3, crect(0.26, 0.42, 0.1, 0.1, oz=0.12)),
    ], by_side({0: {'*': 'black', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                1: {'*': 'black', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                2: {'*': 'cape'}}),
        'frame', None, tip=((0.0, 1.62, -0.14), lambda j: 'cape'))
    # the brow: a black visor over the eye, jutting forward to a point
    brow = H.chevron('brow', 'black',
                     [(-0.42, 0.88), (-0.84, 0.92), (-0.7, 1.08), (-0.4, 1.14)],
                     [(-0.42, 0.9), (-0.6, 0.94), (-0.56, 1.04), (-0.42, 1.1)], 0.42)
    # the eye: a lens standing 0.3 m proud of the mask, glowing all round (the side sees its rim)
    eye = {'id': 'eye', 'op': 'cylinder', 'radius': 0.25, 'height': 0.34, 'segments': 8,
           'material': 'vglow', 'transform': T([0, EYE[1], EYE[2]+0.17], [90, 0, 0])}
    socket = {'id': 'eye_socket', 'op': 'cylinder', 'radius': 0.33, 'height': 0.16,
              'segments': 6, 'material': 'gun', 'faces': {'bottom': 'dark'},
              'transform': T([0, 0.7, -0.46], [90, 0, 0])}
    return [neck, hood, brow, eye, socket]


def pauldron():
    """A narrow shoulder plate (Umbral's mark on its flat outer face) rising to a spike, and a
    cape plate hanging from it outside the upper arm, flaring out at the hem."""
    plate = loft('plate', 'y', [
        (0.68, crect(0.28, 0.36, 0.1, 0.1, ox=0.22)),
        (0.3, crect(0.5, 0.56, 0.16, 0.16, ox=0.32)),
        (-0.25, crect(0.5, 0.56, 0.16, 0.16, ox=0.32)),
        (-0.45, crect(0.4, 0.46, 0.12, 0.12, ox=0.34)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'r': 'emblem'},
                2: {'*': 'frame'}}),
        'frame', 'black')
    spike = plate_yz('spike', [(-0.12, 0.45), (0.5, 0.45), (0.5, 1.3)], 0.12, 'black', 'black',
                     'violet', [0.42, 0, 0])
    cape = plate_yz('shoulder_cape', [(-0.5, 0.05), (0.62, 0.1), (0.78, -2.15), (0.2, -2.6),
                                      (-0.42, -1.9)],
                    0.1, 'cape', 'violet', 'violet', [0.9, -0.05, 0], [0, 0, 7])
    return [plate, spike, cape]


def upper_arm():
    drum = cyl_x('shoulder_drum', 0.36, 0.58, 6, 'frame', [0, 0, 0])
    arm = loft('arm', 'y', [
        (-0.25, crect(0.23, 0.25, 0.08)),
        (-2.35, crect(0.2, 0.22, 0.07)),
    ], lambda k, j: 'gun', None, 'frame')
    return [drum, arm]


def forearm():
    """Long and thin, flaring to a wide cuff at the wrist (violet front edges), an elbow spike
    swept back."""
    drum = cyl_x('elbow_drum', 0.28, 0.5, 6, 'frame', [0, 0, 0])
    arm = loft('gauntlet', 'y', [
        (-0.22, crect(0.24, 0.26, 0.08)),
        (-1.5, crect(0.3, 0.34, 0.1)),
        (-2.25, crect(0.4, 0.44, 0.14, oz=0.02)),
        (-2.5, crect(0.34, 0.38, 0.12, oz=0.02)),
    ], by_side({0: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'fr': 'violet', 'fl': 'violet', 'r': 'cape', 'l': 'cape'},
                2: {'*': 'frame'}}),
        'black', 'frame')
    spike = [(0.12, 0.34), (0.42, 0.05), (1.0, -0.15), (0.32, -0.62)]
    guard = loft('elbow_spike', 'x', [(-0.17, spike), (0.17, spike)],
                 lambda k, j: 'violet' if j == 1 else 'black', 'black', 'black')
    return [drum, arm, guard]


def hand():
    """The big hand: a wrist ball, a palm broad fore and aft (its flats face +-X, so the side
    camera sees it whole), an armoured back plate on the outside with two knuckle spikes. The
    claw mounts at the knuckles, (0, KNUCKLE, 0)."""
    wrist = cyl_x('wrist', 0.24, 0.42, 6, 'gun', [0, 0, 0])
    palm = loft('palm', 'y', [
        (-0.08, crect(0.2, 0.34, 0.08)),
        (-0.62, crect(0.27, 0.62, 0.1, 0.12)),
        (KNUCKLE-0.05, crect(0.24, 0.6, 0.1, 0.12)),
    ], by_side({'*': {'*': 'frame', 'r': 'black', 'f': 'gun', 'b': 'gun'}}), 'gun', 'frame')
    back = plate_yz('back_plate', [(-0.58, -0.3), (0.5, -0.24), (0.66, -1.12), (0.3, -1.5),
                                   (-0.1, -1.18), (-0.42, -1.5), (-0.72, -1.05)],
                    0.12, 'black', 'black', 'violet', [0.32, 0, 0])
    return [wrist, palm, back]


def talon(id_, root, angle, length, curl, w0, t0, mats, segs=3):
    """A talon in the claw's Y-Z plane: from `root` (y, z), `angle` degrees from +Y toward +Z,
    bending `curl` degrees more toward +Z along its length; a diamond section w0 wide (in the
    plane) and t0 thick (in X), tapering to a point. mats: the bands' materials, root first, and
    the tip's last."""
    m = H.Mesh()
    seg = length/(segs+0.6)
    y, z = root
    a = angle
    rings, cents = [], []
    for k in range(segs+1):
        r = math.radians(a)
        d = (math.cos(r), math.sin(r))            # along the talon, (y, z)
        n = (-math.sin(r), math.cos(r))           # across it, in the plane
        f = 1.0-0.62*k/segs
        w, t = w0*f, t0*f
        c = (0.0, y, z)
        ring = [(0.0, y+n[0]*w, z+n[1]*w), (t, y, z), (0.0, y-n[0]*w, z-n[1]*w), (-t, y, z)]
        rings.append([m.vert(p) for p in ring])
        cents.append(c)
        if k < segs:
            y, z = y+d[0]*seg, z+d[1]*seg
            a += curl/segs
    r = math.radians(a)
    tip = m.vert((0.0, y+math.cos(r)*seg*0.6, z+math.sin(r)*seg*0.6))
    for k in range(segs):
        inside = H.mul(H.add(cents[k], cents[k+1]), 0.5)
        r0, r1 = rings[k], rings[k+1]
        for j in range(4):
            q = [r0[j], r0[(j+1) % 4], r1[(j+1) % 4], r1[j]]
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                m.poly(list(tri), mats[k], H.sub(H.cent([m.v[i] for i in tri]), inside))
    last = rings[-1]
    for j in range(4):
        tri = [last[j], last[(j+1) % 4], tip]
        m.poly(tri, mats[-1], H.sub(H.cent([m.v[i] for i in tri]), cents[-1]))
    r0 = math.radians(angle)
    m.poly(list(rings[0]), mats[0], [0, -math.cos(r0), -math.sin(r0)])      # the root's cap
    return m.node(id_), (m.v[tip][1], m.v[tip][2])


# (id, root (y, z), angle, length, curl, width, thickness, sections): the three fingers fanned fore and
# aft from the knuckles, hooked toward -Z, and the thumb from the palm's -Z edge, reaching out
# that way and hooking back against them: from the side, an open grab
TALONS = [
    ('talon_front', (0.0, -0.42), -30, 2.45, -34, 0.24, 0.16, 3),
    ('talon_mid', (0.0, 0.0), 6, 2.9, -28, 0.25, 0.17, 3),
    ('talon_back', (0.0, 0.42), 24, 2.5, -30, 0.24, 0.16, 2),
    ('thumb', (-0.5, -0.64), -70, 2.0, 38, 0.22, 0.15, 2),
]
TRAIL = (0.3, 2.8)       # the trail's base and tip along the claw's +Y (the middle talon's tip: y 2.84, z -0.32)


def claw():
    """The claw (weapon_r and weapon_l: one mesh). Local frame: the knuckles at the origin, +Y out
    along the middle talon, -Z the hand's back (+Z; the talons hook that way), flats facing +-X.
    The talons are gunmetal at the root, pale violet metal along, glowing violet at the tip."""
    out = [box('knuckles', [0.5, 0.42, 1.3], 'black', [0, 0.02, 0.02],
               faces={'top': 'gun', 'bottom': 'gun', 'left': 'violet', 'right': 'violet'})]
    tips = {}
    for id_, root, angle, length, curl, w, t, segs in TALONS:
        mats = ['gun', 'talon', 'vglow', 'vglow'] if segs == 3 else ['gun', 'vglow', 'vglow']
        node, tip = talon(id_, root, angle, length, curl, w, t, mats, segs)
        out.append(node)
        tips[id_] = tip
    return out


def thigh():
    """Long and thin, violet edges down its front corners; the serial plate outside (the second
    band's +X side, flat: the same extents at both its sections)."""
    drum = cyl_x('hip_drum', 0.38, 0.52, 6, 'gun', [0, 0, 0])
    edge = {'fr': 'violet', 'fl': 'violet'}
    arm = loft('thigh', 'y', [
        (-0.28, crect(0.34, 0.4, 0.13)),
        (-0.95, crect(0.4, 0.48, 0.15, oz=-0.04)),
        (-1.55, crect(0.4, 0.48, 0.15, oz=-0.04)),
        (-2.55, crect(0.3, 0.36, 0.1)),
        (-2.75, crect(0.27, 0.32, 0.09)),
    ], by_side({0: {'*': 'black', **edge}, 1: {'*': 'black', 'r': 'serial', **edge},
                2: {'*': 'black', **edge}, 3: {'*': 'frame'}}),
        'frame', 'frame')
    return [drum, arm]


def shin():
    """The long shin: a spiked knee guard, a slim calf, the skirt round the ankle (violet hazard
    stripes) running past the ankle joint, so a pitched foot turns inside it."""
    drum = cyl_x('knee_drum', 0.34, 0.66, 6, 'frame', [0, 0, 0])
    spike = [(-0.2, 0.62), (-0.66, 0.2), (-0.5, -0.5), (-0.24, -0.62)]
    knee = loft('knee_guard', 'x', [(-0.36, spike), (0.36, spike)],
                lambda k, j: 'violet' if j == 0 else 'black', 'black', 'black')
    leg = loft('shin', 'y', [
        (-0.32, crect(0.3, 0.36, 0.11, oz=0.04)),
        (-1.35, crect(0.38, 0.54, 0.14, 0.2, oz=0.12)),
        (-2.45, crect(0.34, 0.42, 0.12, oz=0.04)),
        (-2.75, crect(0.4, 0.48, 0.14, 0.16, oz=0.02)),
        (-3.08, crect(0.38, 0.46, 0.13, 0.15)),
    ], by_side({0: {'*': 'black', 'f': 'cape', 'fr': 'violet', 'fl': 'violet'},
                1: {'*': 'black', 'fr': 'violet', 'fl': 'violet'},
                2: {'*': 'gun'},
                3: {'*': 'frame', 'r': 'hazard', 'l': 'hazard'}}),
        'frame', 'frame')
    return [drum, knee, leg]


def foot():
    """Long and pointed, a heel talon swept back; the instep rises into the shin's skirt."""
    drum = cyl_x('ankle_drum', 0.32, 0.62, 6, 'frame', [0, 0, 0])
    prof = [(0.6, -0.8), (0.66, -0.45), (0.25, -0.1), (-0.5, -0.3), (-1.55, -0.62),
            (-1.95, -0.8), (-1.5, -0.82)]
    smat = ['black', 'black', 'gun', 'black', 'violet', 'dark', 'dark']
    shoe = loft('shoe', 'x', [(-0.4, prof), (0.4, prof)], lambda k, j: smat[j], 'black', 'black')
    spur = plate_yz('heel_talon', [(0.45, -0.42), (1.2, -0.78), (0.55, -0.8)], 0.14, 'talon',
                    'talon', 'gun', [0, 0, 0])
    return [drum, shoe, spur]


PARTS = {
    'pelvis': pelvis, 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': hand, 'claw': claw,
    'thigh': thigh, 'shin': shin, 'foot': foot,
}
SIDED = {'pauldron', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot'}


def geometry(part, side):
    return H.geometry(part, side, PARTS)


# ---- the skeleton, posing, assembling --------------------------------------------------------

def skeleton():
    """(id, parent, offset, rest rotation, part, side), parents first: the Hero's ids and order
    (make_hero.skeleton) with Shadow's offsets; the claws on mounts at the knuckles."""
    out = [('pelvis', None, [0, HIP_Y, 0], None, 'pelvis', None),
           ('torso', 'pelvis', [0, WAIST, 0], None, 'torso', None),
           ('head', 'torso', list(NECK), None, 'head', None)]
    for s in 'rl':
        x = SHOULDER[0] if s == 'l' else -SHOULDER[0]
        at = [x, SHOULDER[1], SHOULDER[2]]
        out += [(f'pauldron_{s}', 'torso', at, None, 'pauldron', s),
                (f'upper_arm_{s}', 'torso', at, None, 'upper_arm', s),
                (f'forearm_{s}', f'upper_arm_{s}', [0, -UPPER, 0], None, 'forearm', s),
                (f'hand_{s}', f'forearm_{s}', [0, -FORE, 0], None, 'hand', s),
                (f'weapon_{s}', f'hand_{s}', [0, KNUCKLE, 0], CLAW_REST, 'claw', None)]
    for s in 'rl':
        x = HIP_X if s == 'l' else -HIP_X
        out += [(f'thigh_{s}', 'pelvis', [x, 0, 0], None, 'thigh', s),
                (f'shin_{s}', f'thigh_{s}', [0, -THIGH, 0], None, 'shin', s),
                (f'foot_{s}', f'shin_{s}', [0, -SHIN, 0], None, 'foot', s)]
    return out


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


def solve_leg(side, stance, drop):
    """Knee and ankle angles that put this ankle ANKLE above the ground with the sole level."""
    def ankle_y(k):
        st = dict(stance)
        st[f'shin_{side}'] = [k, 0, 0]
        return world_frames(st, drop)[f'foot_{side}'][1][1]
    lo, hi = -150.0, 0.0
    for _ in range(60):
        mid = (lo+hi)/2
        if ankle_y(mid) > ANKLE+0.01:
            lo = mid
        else:
            hi = mid
    k = round((lo+hi)/2, 2)
    px, th = stance.get('pelvis', [0, 0, 0])[0], stance[f'thigh_{side}']
    return [k, 0, 0], [round(-(px+th[0]+k), 2), 0, round(-th[2], 2)]


def pose(base, drop):
    st = dict(base)
    for s in 'rl':
        ua = st.get(f'upper_arm_{s}', [0, 0, 0])
        st[f'pauldron_{s}'] = [round(ua[0]*0.35, 2), 0, round(ua[2]*0.5, 2)]
    for s in 'rl':
        if f'thigh_{s}' in st and f'shin_{s}' not in st:
            st[f'shin_{s}'], st[f'foot_{s}'] = solve_leg(s, st, drop)
    return st


def assemble(stance, drop=0.0):
    """The rig as nested groups, posed. A joint's rest rotation (the claws') comes before its
    pose: a group for the rest, the posed group inside it."""
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


def used_materials(nodes):
    return {k: v for k, v in MATERIALS.items() if k in H.used(nodes)}


def recipe(name, nodes, budget, vertices=2048):
    r = H.recipe(name, nodes, budget, vertices, materials=MATERIALS)
    r['materials'] = used_materials(nodes)
    return r


# ---- the guard: low and wide-armed, claws forward and open, the cape hanging -----------------
# The right side (-X) leads, as the Hero's: right foot forward. Crouched low on its long legs,
# leaning in, the head up; both arms spread wide and reaching forward, the claws held out in
# front, talons spread, the lead claw high and the rear one low.

DROP = 1.1
STANCE = pose({
    'pelvis': [0, -8, 0], 'torso': [-14, -8, 0], 'head': [16, 8, 0],
    'thigh_r': [34, 0, -11], 'thigh_l': [-12, 0, 12],
    'upper_arm_r': [64, 0, -26], 'forearm_r': [34, 0, 12], 'hand_r': [-24, 0, 0],
    'weapon_r': [6, 0, 0],
    'upper_arm_l': [36, 0, 30], 'forearm_l': [44, 0, -10], 'hand_l': [-10, 0, 0],
    'weapon_l': [6, 0, 0],
}, DROP)
# The pitched pelvis leaves the soles a little off level (a toe 3 cm into the floor): the mech is
# drawn 3 cm higher than the knees were solved for.
DRAWN_DROP = DROP - 0.03

# ---- the flex check: each joint near the end of its range -------------------------------------

FLEX_DROP = 1.9
FLEX = pose({
    'pelvis': [10, 0, 0], 'torso': [22, 28, -6], 'head': [-26, -24, 0],
    'upper_arm_r': [165, 0, -12], 'forearm_r': [70, 0, 0], 'hand_r': [-55, 0, 0],
    'weapon_r': [40, 0, 0],
    'upper_arm_l': [-45, 0, 34], 'forearm_l': [135, 0, 0], 'hand_l': [55, 0, 20],
    'weapon_l': [-30, 0, 0],
    'thigh_r': [95, 0, -4], 'shin_r': [-125, 0, 0], 'foot_r': [-38, 0, 0],
    'thigh_l': [-28, 0, 6], 'shin_l': [-70, 0, 0], 'foot_l': [42, 0, 0],
}, FLEX_DROP)


# ---- cameras ---------------------------------------------------------------------------------

def cameras(stance, drop):
    """Side views at game distance (31.2 m: about 80 px), nearer ones, quarters, the head close
    up and each claw."""
    mid, mz = 5.8, -2.0
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_facing_left', 'eye': [31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_right_near', 'eye': [-17.0, 6.0, mz], 'target': [0, 6.0, mz]},
        {'name': 'side_left_near', 'eye': [17.0, 6.0, mz], 'target': [0, 6.0, mz]},
        {'name': 'front_quarter', 'eye': [-12.0, 9.0, -16.0], 'target': [0, 6.0, -1.5]},
        {'name': 'back_quarter', 'eye': [12.0, 9.0, 14.0], 'target': [0, 6.0, 0.0]},
        {'name': 'front', 'eye': [0, 6.5, -20.0], 'target': [0, 6.0, 0]},
        {'name': 'back_close', 'eye': [-7.5, 9.5, 9.0], 'target': [0, 7.0, 1.2]},
    ]
    fr = world_frames(stance, drop)
    hr, hp = fr['head']
    hc = H.add(hp, H.mv(hr, [0, 0.8, -0.2]))
    for name, dv in (('head_front', [0, 0.25, -1]), ('head_side_right', [-1, 0.2, 0]),
                     ('head_side_left', [1, 0.2, 0]), ('head_three_quarter', [-0.75, 0.35, -0.7])):
        v = H.mv(hr, dv)
        ln = math.sqrt(H.dot(v, v))
        cams.append({'name': name, 'eye': [round(hc[k]+v[k]*4.0/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in hc]})
    for sd, sx in (('r', -1), ('l', 1)):
        r, p = fr[f'weapon_{sd}']
        c = H.add(p, H.mv(r, [0, 1.0, 0.2]))
        for name, dv in (('out', [sx, 0.2, 0]), ('front', [sx*0.5, 0.3, -1])):
            ln = math.sqrt(H.dot(dv, dv))
            cams.append({'name': f'claw_{sd}_{name}', 'eye': [round(c[k]+dv[k]*5.5/ln, 3) for k in range(3)],
                         'target': [round(v, 3) for v in c]})
    return cams


def flex_cameras(stance, drop):
    cams = [
        {'name': 'flex_side_right', 'eye': [-17.0, 5.2, -1.0], 'target': [0, 5.2, -1.0]},
        {'name': 'flex_side_left', 'eye': [17.0, 5.2, -1.0], 'target': [0, 5.2, -1.0]},
        {'name': 'flex_front_quarter', 'eye': [-11.0, 7.0, -13.0], 'target': [0, 5.0, -1.0]},
    ]
    fr = world_frames(stance, drop)
    for jid, dv, dist in (('foot_r', [-1, 0.3, -0.2], 4.2), ('foot_l', [1, 0.3, 0.1], 4.2),
                          ('shin_r', [-1, 0.2, 0.3], 4.5), ('shin_l', [1, 0.2, -0.2], 4.5),
                          ('forearm_l', [1, 0.3, -0.3], 4.0), ('hand_r', [-1, 0.2, -0.4], 4.5),
                          ('hand_l', [0.8, 0.3, -0.8], 4.5), ('torso', [-1, 0.2, -0.6], 6.0),
                          ('upper_arm_r', [-1, 0.0, -0.3], 4.5)):
        _, p = fr[jid]
        ln = math.sqrt(H.dot(dv, dv))
        cams.append({'name': f'flex_{jid}', 'eye': [round(p[k]+dv[k]*dist/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in p]})
    return cams


# ---- writing ---------------------------------------------------------------------------------

def claw_tips():
    """{talon id: (y, z)}: each talon's tip in the claw's frame."""
    return {id_: talon(id_, root, a, ln, c, w, t, ['gun']*4, n)[1]
            for id_, root, a, ln, c, w, t, n in TALONS}


ALLOW = [['forearm_r', 'weapon_r'], ['forearm_l', 'weapon_l'], ['torso', 'thigh_r'],
         ['torso', 'thigh_l']]


def write_rig(stance, drop, part_recipes, height):
    parts = []
    for jid, parent, offset, rest, part, side in skeleton():
        pname = H.part_name('shadow', part, side)
        e = {'id': jid, 'parent': parent, 'offset': [round(c, 4) for c in offset]}
        if rest:
            e['rotate'] = rest
        e['recipe'] = f'parts/{pname}.asset.json'
        e['asset'] = f'ASSET_{pname.upper()}'
        e.update(H.part_facts(part_recipes[pname]))
        role, rng = RANGES['weapon' if part == 'claw' else part]
        e['role'] = role
        e['range'] = rng
        parts.append(e)
    tips = {k: [0.0, round(y, 3), round(z, 3)] for k, (y, z) in claw_tips().items()}
    mounts = [{'id': f'weapon_{s}', 'parent': f'hand_{s}', 'offset': [0, KNUCKLE, 0],
               'rotate': CLAW_REST, 'part': f'weapon_{s}',
               'note': "the knuckles; the claw's +Y runs out along the middle talon (the hand's "
                       "-Y), its -Z is the hand's +Z, the way the talons hook"}
              for s in 'rl']
    rig = {
        'format': 'mei-rig', 'version': 1, 'name': 'shadow',
        'units': 'metres; Y up; the mech faces -Z, +X is its left',
        'rotation': 'degrees, applied X then Y then Z, in the parent joint frame (the Asset Kit\'s '
                    'order). Not mirrored between sides: on a hanging limb +X swings it forward; '
                    '+Z swings a left limb out (+X) and a right limb in, so a mirrored pose negates '
                    'Y and Z',
        'root': 'pelvis',
        'root_note': "the root (fight origin) is on the floor under the pelvis; pelvis.offset is "
                     "the rest-pose hip-axle height, a pose lowers it by its 'drop'",
        'body': "Umbral Research's Shadow (UR-01): tall and thin, long arms, big hands with "
                "claws (the weapon parts), rigid cape plates on the torso and the pauldrons, one "
                "eye",
        'height': height,
        'parts': parts,
        'mounts': mounts,
        'claw': {
            'note': "The claws are weapon_r and weapon_l (one mesh): for the trails, sample the "
                    "weapon part's +Y from 'trail' base to tip (the middle talon). The talons "
                    "fan fore and aft in the claw's Y-Z plane (the plane the side camera sees) "
                    "and hook toward its -Z; 'tips' gives each talon's point in the claw's frame. "
                    "Turn the hand about Y (its twist) to turn the claw's flat toward or away "
                    "from the camera; at y 0 or 180 the side camera sees the fan whole",
            'trail': list(TRAIL),
            'tips': tips,
        },
        'eye': {'part': 'head', 'point': list(EYE),
                'note': "the single eye's front face, in the head's frame (for the eye flare); it "
                        "looks along the head's -Z"},
        'poses': {'guard': {'drop': round(drop, 4), 'rotate': dict(stance),
                            'note': 'low and wide-armed: crouched on its long legs, leaning in, '
                                    'both arms spread and reaching forward, the claws out in front '
                                    'and open (the lead claw high, the rear one low), the cape '
                                    'hanging; both soles on y = 0'}},
        'allow': ALLOW,
        'allow_note': "pairs of parts every move may pass into each other (a move's \"allow\" adds "
                      "more): a bent wrist puts the claw's knuckles into the forearm's cuff, and a "
                      "thigh swung far back meets the cape's hem (the cape is the torso's)",
        'triangles': sum(p['triangles'] for p in parts),
    }
    H.write(HERE/'shadow.rig.json', rig)
    return rig


def height():
    """The rest pose's top (from the assembled recipe's bounds)."""
    return H.part_facts(recipe('h', assemble({}), 4000))['bounds']['max'][1]


def main():
    budget = 1800
    H.write(HERE/'shadow.asset.json', recipe('shadow', assemble(STANCE, DRAWN_DROP), budget))
    H.write(HERE/'shadow_rest.asset.json', recipe('shadow_rest', assemble({}), budget))
    written = {}
    for part in PARTS:
        for side in (('l', 'r') if part in SIDED else (None,)):
            pname = H.part_name('shadow', part, side)
            r = recipe(pname, geometry(part, side), 400, 512)
            H.write(HERE/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    for p in (HERE/'parts').glob('shadow_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    H.write(HERE/'shadow_flex.asset.json', recipe('shadow_flex', assemble(FLEX, FLEX_DROP), budget))
    H.write(HERE/'cameras.json', cameras(STANCE, DRAWN_DROP))
    H.write(HERE/'cameras_flex.json', flex_cameras(FLEX, FLEX_DROP))
    H.write(HERE/'asset-preview.json', LOOK)
    h = round(height(), 3)
    rig = write_rig(STANCE, DRAWN_DROP, written, h)
    print(f'shadow: {rig["triangles"]} triangles, {h} m tall')


if __name__ == '__main__':
    main()
