#!/usr/bin/env python3
"""Mech Expo 2000: the Hero Mech (Momentum Robotics), production pass.

Its rig, part builders and writers are shared with its echoes (../doubleblade/), which import
this module: change a shared part here and the echo changes with it.

Writes, beside this script:

  hero.asset.json         the whole mech, assembled in its fighting stance: a group per rigid
                          part, nested as the rig is (pelvis > torso > upper arm > ...), each
                          part's geometry authored with its origin at its joint
  hero_rest.asset.json    the same in the rest pose (every joint at 0): standing height
  parts/hero_*.asset.json each rigid part alone, its origin at its joint, as a cart would pack
                          them for mesh_xf() (the way carts/garden/robot/ is built)
  hero_flex.asset.json    the same in a pose that bends every joint far (deep knee, pitched feet,
                          an arm overhead, a bent wrist), for checking that joints stay whole;
                          not packed
  hero.rig.json           the rig (carts/mechexpo/README.md, "Rig (B) -> Animation Kit (A)")
  cameras.json, cameras_flex.json   the preview's views: side views at game distance (about
                          80 px tall, both facings), nearer ones and close-ups
  momentum_emblem.png     Momentum Robotics' mark, 256 x 256 with transparency, for the menus

The emblem, the serial plate and the hazard stripes are texel grids drawn in code (mxpaint.py).
Run from anywhere: python3 carts/mechexpo/models/hero/make_hero.py
Standard library only.

Conventions: 1 unit = 1 m, Y up, the mech faces -Z. Its left side is +X (the front camera
sees it on the right). Left-side parts are authored with +X outward; the right-side parts are
the same shapes mirrored (a group scaled -1 in X). Rotations are the kit's: degrees, X then Y
then Z; on a hanging limb a positive X swings it forward (toward -Z).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mxpaint as P  # noqa: E402

# ---- palette (STYLE.md: Momentum is red with white accents and chrome trim; one glow) -------

MATERIALS = {
    'red':    {'color': '#e8262c'},
    'white':  {'color': '#f6f6f2'},
    'chrome': {'color': '#c6d0dc', 'smooth': True},
    'frame':  {'color': '#4c5462'},           # the neutral metal: joints, frame, upper arms
    'dark':   {'color': '#262a33'},           # soles, grip, the mouth vents
    'steel':  {'color': '#dfe8f2'},           # the blade's flats
    'glow':   {'color': '#8ff4ff', 'class': 'emissive'},   # eyes / visor
    'edge':   {'color': '#f4fcff', 'class': 'emissive'},   # the blade's bevels: long and bright
}
# The trade-show finish, as textures drawn once over a face (fit) or repeating (hazard).
# EMBLEM_TEX: the mark on a field, 56 x 32 for the pauldron's 1.34 x 0.78 m outer panel.


def emblem_texture(shapes, field, w=56, h=32, pad=2):
    d = h-2*pad
    return P.texels(P.scaled(shapes, d/w, d/h, (w-d)/2/w, pad/h), w, h, field)


MATERIALS.update({
    'emblem': {'color': '#e8262c', 'texture': {**emblem_texture(P.emblem_momentum(), '#e8262c'),
                                               'projection': 'fit'}},
    'serial': {'color': '#f6f6f2', 'texture': {**P.serial_plate('MR-01', '#f6f6f2', '#262a33'),
                                               'projection': 'fit'}},
    'hazard': {'color': '#f2c200', 'texture': {**P.hazard(['#f2c200', '#22242a']),
                                               'projection': 'box', 'scale': [0.32, 0.32]}},
})

# Light from above and in front, with no X component: the side camera sees either flank
# depending on the facing, and both must look alike. Fronts are lit, flanks and backs get the
# ambient, so front and back read apart.
LIGHTING = {'direction': [0, 0.62, -0.78], 'ambient': 0.66}
POLICY = {'required': True, 'depth': True, 'perspective': True}


# ---- a small mesh builder -------------------------------------------------------------------

def sub(a, b): return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
def add(a, b): return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]
def mul(a, s): return [a[0]*s, a[1]*s, a[2]*s]
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def cent(pts): return mul([sum(p[k] for p in pts) for k in range(3)], 1/len(pts))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i+1) % len(pts)]
        n[0] += (p[1]-q[1])*(p[2]+q[2])
        n[1] += (p[2]-q[2])*(p[0]+q[0])
        n[2] += (p[0]-q[0])*(p[1]+q[1])
    return n


class Mesh:
    """Vertices and polygons with a material each, wound outward from a point inside."""

    def __init__(self):
        self.v, self.f, self.fm = [], [], []

    def vert(self, p):
        self.v.append([round(c, 5) for c in p])
        return len(self.v)-1

    def poly(self, idx, mat, want):
        pts = [self.v[i] for i in idx]
        if dot(newell(pts), want) < 0:
            idx = idx[::-1]
        self.f.append(list(idx))
        self.fm.append(mat)

    def node(self, id_):
        return {'id': id_, 'op': 'mesh', 'vertices': self.v, 'faces': self.f,
                'face_materials': self.fm}


def place(axis, t, a, b):
    """A section point: along `axis` at t, (a, b) across it. y: (x, z); x: (z, y); z: (x, y)."""
    if axis == 'y':
        return (a, t, b)
    if axis == 'x':
        return (t, b, a)
    return (a, b, t)


def loft(id_, axis, secs, mat, cap0, cap1, tip=None):
    """A solid through sections along an axis. secs: [(t, [(a, b), ...]), ...], every section
    the same count of points in the same order (a convex outline). mat(k, j): the material of
    band k (between sections k and k+1), side j (from point j to j+1). cap0 / cap1: the first and
    last section's caps (None: no cap). tip: (point, mat(j)) closes the last section to a point
    instead of a cap. Each band quad is given as two triangles, so no quad need be planar."""
    m = Mesh()
    rings = [[m.vert(place(axis, t, a, b)) for a, b in pts] for t, pts in secs]
    cents = [cent([m.v[i] for i in r]) for r in rings]
    n = len(rings[0])
    for k in range(len(rings)-1):
        r0, r1 = rings[k], rings[k+1]
        inside = mul(add(cents[k], cents[k+1]), 0.5)
        for j in range(n):
            a, b, c, d = r0[j], r0[(j+1) % n], r1[(j+1) % n], r1[j]
            mt = mat(k, j)
            for tri in ((a, b, c), (a, c, d)):
                w = sub(cent([m.v[i] for i in tri]), inside)
                m.poly(list(tri), mt, w)
    ax = {'x': [1, 0, 0], 'y': [0, 1, 0], 'z': [0, 0, 1]}[axis]
    sgn = 1 if secs[-1][0] > secs[0][0] else -1
    if cap0:
        m.poly(list(rings[0]), cap0, mul(ax, -sgn))
    if tip:
        p, tmat = tip
        ti = m.vert(p)
        inside = cents[-1]
        r = rings[-1]
        for j in range(n):
            tri = [r[j], r[(j+1) % n], ti]
            m.poly(tri, tmat(j), sub(cent([m.v[i] for i in tri]), inside))
    elif cap1:
        m.poly(list(rings[-1]), cap1, mul(ax, sgn))
    return m.node(id_)


def crect(w, d, cf, cb=None, ox=0.0, oz=0.0):
    """A rectangle 2w x 2d with its front (-Z) corners cut by cf and its back corners by cb,
    centred on (ox, oz). Its sides in order (loft's j): fr, r, br, b, bl, l, fl, f."""
    cb = cf if cb is None else cb
    pts = [(w-cf, -d), (w, -d+cf), (w, d-cb), (w-cb, d), (-w+cb, d), (-w, d-cb), (-w, -d+cf),
           (-w+cf, -d)]
    return [(x+ox, z+oz) for x, z in pts]


SIDES = ['fr', 'r', 'br', 'b', 'bl', 'l', 'fl', 'f']
FRONT = {'f', 'fr', 'fl'}


def by_side(table):
    """mat(k, j) from {band: {side: material, '*': default}}; bands missing use table['*']."""
    def mat(k, j):
        row = table.get(k, table.get('*'))
        return row.get(SIDES[j], row['*'])
    return mat


def T(translate=None, rotate=None, scale=None):
    t = {}
    if scale:
        t['scale'] = scale
    if rotate:
        t['rotate'] = rotate
    if translate:
        t['translate'] = translate
    return t


def cyl_x(id_, r, length, seg, mat, at, faces=None):
    """A drum along X (a hinge, an axle), centred at `at`."""
    n = {'id': id_, 'op': 'cylinder', 'radius': r, 'height': length, 'segments': seg,
         'material': mat, 'transform': T(at, [0, 0, 90])}
    if faces:
        n['faces'] = faces
    return n


def box(id_, size, mat, at, rotate=None, faces=None, open_=None):
    n = {'id': id_, 'op': 'box', 'size': size, 'material': mat,
         'transform': T(at, rotate)}
    if faces:
        n['faces'] = faces
    if open_:
        n['open'] = open_
    return n


# ---- the rig: rest-pose joints (in the parent's frame) ---------------------------------------

THIGH, SHIN, ANKLE = 2.6, 2.5, 0.85     # hip to knee, knee to ankle, ankle above the sole
HIP_X = 1.05
WAIST = 0.7                             # pelvis (hip axle) to the waist joint
SHOULDER = (2.3, 2.85, 0.05)            # from the waist joint
NECK = (0.0, 3.62, -0.1)
UPPER, FORE = 2.2, 2.0                  # shoulder to elbow, elbow to wrist
GRIP = -0.42                            # wrist to the middle of the fist


# ---- the parts (left / centre, origin at the joint) -----------------------------------------

def pelvis():
    core = loft('core', 'y', [
        (0.55, crect(0.80, 0.62, 0.24, 0.2)),
        (0.05, crect(0.92, 0.70, 0.28, 0.22)),
        (-0.50, crect(0.56, 0.56, 0.2, 0.16, oz=-0.05)),
        (-0.92, crect(0.28, 0.40, 0.1, 0.1, oz=-0.05)),
    ], by_side({0: {'*': 'red'},
                1: {'*': 'frame', 'f': 'white', 'fr': 'white', 'fl': 'white'},
                2: {'*': 'frame', 'f': 'white', 'fr': 'white', 'fl': 'white'}}),
        'frame', 'frame')
    skirt = {'id': 'side_skirts', 'op': 'group', 'children': [
        box('skirt', [0.16, 1.3, 1.25], 'chrome', [1.56, -0.12, 0], [0, 0, 8],
            faces={'right': 'red', 'left': 'red'}),
        box('skirt_mount', [0.72, 0.26, 0.56], 'frame', [1.18, 0.44, 0])],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    rear = box('rear_skirt', [1.3, 1.0, 0.18], 'red', [0, -0.25, 0.8], [-12, 0, 0])
    return [core, skirt, rear]


def torso():
    abdomen = loft('abdomen', 'y', [
        (-0.2, crect(0.60, 0.52, 0.18)),
        (0.45, crect(0.68, 0.58, 0.2)),
        (1.0, crect(0.75, 0.62, 0.22)),
    ], by_side({0: {'*': 'frame'}, 1: {'*': 'chrome'}}), 'frame', 'frame')
    chest = loft('chest', 'y', [
        (0.9, crect(1.00, 0.72, 0.30, 0.25)),
        (1.7, crect(1.55, 1.00, 0.45, 0.30, oz=-0.08)),
        (2.45, crect(1.78, 1.12, 0.50, 0.35, oz=-0.12)),
        (3.05, crect(1.60, 1.02, 0.45, 0.30, oz=-0.06)),
        (3.4, crect(1.05, 0.80, 0.30, 0.25, oz=0.02)),
    ], by_side({0: {'*': 'red'},
                1: {'*': 'red', 'fr': 'white', 'fl': 'white'},
                2: {'*': 'red', 'fr': 'white', 'fl': 'white'},
                3: {'*': 'chrome'}}),
        'frame', 'frame')
    sockets = cyl_x('shoulder_sockets', 0.42, 2*SHOULDER[0]-0.4, 6, 'frame',
                    [0, SHOULDER[1], SHOULDER[2]])
    collar = loft('collar', 'y', [
        (3.3, crect(0.72, 0.56, 0.2)),
        (3.66, crect(0.58, 0.46, 0.16)),
    ], lambda k, j: 'white', None, 'frame')
    mount = box('pack_mount', [1.2, 1.3, 0.9], 'frame', [0, 2.1, 1.05])
    # Momentum's kinetic power: a flywheel on the back, its axle along X, so the side camera
    # sees it as a wheel. It sets the back apart from the front at a glance.
    flywheel = cyl_x('flywheel', 1.0, 1.3, 10, 'red', [0, 2.25, 1.75],
                     faces={'top': 'chrome', 'bottom': 'chrome'})
    hub = cyl_x('hub', 0.4, 1.62, 6, 'frame', [0, 2.25, 1.75])
    return [abdomen, chest, sockets, collar, mount, flywheel, hub]


# The helmet's sections (y, then crect's w, d, cf, cb, oz): shared with the echoes' heads.
HELMET_SPEC = [
    (0.28, 0.46, 0.50, 0.18, 0.14, 0.02),
    (0.60, 0.60, 0.64, 0.26, 0.18, 0.0),
    (0.84, 0.64, 0.68, 0.28, 0.18, -0.02),
    (1.25, 0.60, 0.64, 0.26, 0.18, 0.0),
    (1.48, 0.36, 0.44, 0.14, 0.12, 0.04),
]
HELMET = [(y, crect(w, d, cf, cb, oz=oz)) for y, w, d, cf, cb, oz in HELMET_SPEC]


def chevron(id_, mat, full, side, half):
    """A wedge across the face, its `full` profile (z, y) in the middle and `side` at x = +-half:
    a chevron from the front."""
    return loft(id_, 'x', [(-half, side), (0.0, full), (half, side)],
                lambda k, j: mat, mat, mat)


def head():
    """The face. Second pass: a third bigger than the first sketch, with a profile built to
    read side-on at game distance: a red brow prow jutting over the glowing visor, a chrome jaw
    under it, a red crest swept back past the nape like a speed fin (Momentum: kinetic), and
    two broad white wings from the temples, swept back, that make the V from the front."""
    neck = {'id': 'neck', 'op': 'cylinder', 'radius': 0.34, 'height': 0.6, 'segments': 6,
            'material': 'frame', 'transform': T([0, 0.2, 0])}
    helmet = loft('helmet', 'y', HELMET, by_side({0: {'*': 'white', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                1: {'*': 'white', 'f': 'glow', 'fr': 'glow', 'fl': 'glow'},
                2: {'*': 'white'},
                3: {'*': 'white'}}),
        'frame', 'white')
    # the brow juts 0.3 past the visor: the profile's nose
    brow = chevron('brow', 'red',
                   [(-0.52, 0.86), (-1.02, 0.84), (-0.94, 1.0), (-0.52, 1.26)],
                   [(-0.52, 0.88), (-0.74, 0.88), (-0.72, 0.98), (-0.52, 1.18)], 0.62)
    jaw = chevron('jaw', 'chrome',
                  [(-0.48, 0.3), (-0.84, 0.36), (-0.88, 0.54), (-0.5, 0.6)],
                  [(-0.48, 0.32), (-0.68, 0.38), (-0.7, 0.52), (-0.5, 0.58)], 0.5)
    # the crest rises from the brow and sweeps back past the nape
    fin = [(-0.62, 1.2), (-0.3, 1.74), (1.1, 2.02), (0.45, 1.45)]
    crest = loft('crest', 'x', [(-0.09, fin), (0.09, fin)], lambda k, j: 'red', 'red', 'red')
    # broad wings from the temples: out, up and swept 28 degrees back; a solid V from the front
    wings = {'id': 'wings', 'op': 'group', 'children': [
        {'id': 'wing', 'op': 'extrude', 'depth': 0.12, 'material': 'white',
         'faces': {'side': 'chrome'},
         'points': [[0.32, 0.98], [0.30, 1.24], [1.22, 1.8], [0.72, 1.26]],
         'transform': {'pivot': [0.31, 1.1, 0], 'rotate': [0, -28, 0],
                       'translate': [0, 0, -0.42]}}],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    # red roundels on the temples, chrome-rimmed: the Momentum mark, seen side-on
    ears = cyl_x('ears', 0.3, 1.42, 8, 'chrome', [0, 0.74, 0.08],
                 faces={'top': 'red', 'bottom': 'red'})
    return [neck, helmet, brow, jaw, crest, wings, ears]


def pauldron():
    """The shoulder plate. Its outer side (+X) between the second and third sections is one flat
    rectangle (the same x, z extents at both), so Momentum's emblem is drawn on it whole."""
    plate = loft('plate', 'y', [
        (0.82, crect(0.50, 0.58, 0.18, 0.16, ox=0.18)),
        (0.36, crect(0.86, 0.95, 0.30, 0.26, ox=0.37)),
        (-0.42, crect(0.80, 0.95, 0.30, 0.26, ox=0.43)),
        (-0.62, crect(0.72, 0.84, 0.24, 0.2, ox=0.44)),
    ], by_side({0: {'*': 'white'}, 1: {'*': 'red', 'r': 'emblem'}, 2: {'*': 'chrome'}}),
        'frame', 'white')
    return [plate]


def upper_arm():
    drum = cyl_x('shoulder_drum', 0.5, 0.72, 8, 'frame', [0, 0, 0])
    arm = loft('arm', 'y', [
        (-0.3, crect(0.34, 0.36, 0.12)),
        (-1.95, crect(0.30, 0.33, 0.1)),
    ], lambda k, j: 'frame', None, 'frame')
    return [drum, arm]


def forearm():
    drum = cyl_x('elbow_drum', 0.38, 0.62, 6, 'chrome', [0, 0, 0])
    arm = loft('gauntlet', 'y', [
        (-0.3, crect(0.38, 0.40, 0.14)),
        (-1.05, crect(0.50, 0.54, 0.18, oz=0.04)),
        (-1.6, crect(0.46, 0.50, 0.16, oz=0.02)),
        (-1.85, crect(0.40, 0.44, 0.14, oz=0.02)),
    ], by_side({0: {'*': 'red'}, 1: {'*': 'red', 'r': 'white'}, 2: {'*': 'chrome'}}),
        'red', 'frame')
    # an elbow guard behind the joint, so the bent elbow still looks whole
    guard = loft('elbow_guard', 'x', [
        (-0.37, [(0.22, 0.42), (0.58, 0.16), (0.6, -0.55), (0.3, -0.75)]),
        (0.37, [(0.22, 0.42), (0.58, 0.16), (0.6, -0.55), (0.3, -0.75)]),
    ], lambda k, j: 'white', 'white', 'white')
    return [drum, arm, guard]


def hand():
    """A fist closed round a grip along Z through (0, GRIP, 0): the weapon mount. The back of the
    hand (+X, outward) is an armoured plate from the wrist; the fingers wrap the grip, the thumb
    lies over it at the front (-Z), toward the guard. The wrist is a ball (a short drum) so a
    bent wrist stays whole. Empty, it is a fist."""
    wrist = cyl_x('wrist', 0.22, 0.48, 6, 'chrome', [0, 0, 0])
    g = GRIP
    # the fingers, round the grip: an outline across X-Y (z the grip's axis), front to back
    sec = [(0.31, g+0.2), (0.33, g-0.12), (0.17, g-0.27), (-0.27, g-0.17), (-0.27, g+0.16),
           (0.02, g+0.26)]
    fist = loft('fist', 'z', [(-0.29, sec), (0.25, [(x*0.94, g+(y-g)*0.94) for x, y in sec])],
                by_side({'*': {'*': 'frame'}}), 'dark', 'frame')
    # the back of the hand: an armoured plate from the wrist down over the outside of the fingers
    back = box('back', [0.15, 0.64, 0.42], 'red', [0.37, g/2-0.06, -0.01], [0, 0, 4],
               faces={'left': 'frame'})
    thumb = box('thumb', [0.2, 0.17, 0.3], 'red', [-0.16, g+0.2, -0.24], [0, 0, -18])
    return [wrist, fist, back, thumb]


def sword():
    """Local frame: the grip's middle at the origin, the blade along +Y, its width along Z (the
    cutting edge +Z), its flats facing +-X. The hand turns it to point out of the fist (-Z)."""
    grip = {'id': 'grip', 'op': 'cylinder', 'radius': 0.14, 'height': 1.2, 'segments': 6,
            'material': 'dark', 'transform': T([0, -0.05, 0])}
    pommel = box('pommel', [0.26, 0.24, 0.42], 'chrome', [0, -0.72, 0])
    sec = [(0.2, 0.48), (0.3, 0.6), (0.2, 0.74), (-0.2, 0.74), (-0.3, 0.6), (-0.2, 0.48)]
    guard = loft('guard', 'z', [
        (-0.85, [(x*0.6, 0.61+(y-0.61)*0.6) for x, y in sec]),
        (0.0, sec),
        (0.85, [(x*0.6, 0.61+(y-0.61)*0.6) for x, y in sec]),
    ], lambda k, j: 'red', 'white', 'white')
    disc = cyl_x('flywheel_disc', 0.3, 0.74, 6, 'chrome', [0, 0.61, 0])

    def blade_sec(hw, ht, flat):
        # (x, z): bevel to the edges at z = +-hw, flats at x = +-ht between z = +-flat
        return [(0.0, hw), (ht, flat), (ht, -flat), (0.0, -hw), (-ht, -flat), (-ht, flat)]

    def bmat(k, j):
        return 'steel' if j in (1, 4) else 'edge'
    blade = loft('blade', 'y', [
        (0.72, blade_sec(0.36, 0.09, 0.12)),
        (3.8, blade_sec(0.36, 0.09, 0.12)),
        (6.3, blade_sec(0.33, 0.08, 0.11)),
    ], bmat, 'steel', None, tip=((0.0, 7.2, 0.14), lambda j: bmat(0, j)))
    return [grip, pommel, guard, disc, blade]


def thigh():
    """The thigh. Its outer side carries the serial plate: a flat white panel (the second band's
    +X side, the same extents at both its sections)."""
    drum = cyl_x('hip_drum', 0.5, 0.62, 8, 'chrome', [0, 0, 0])
    arm = loft('thigh', 'y', [
        (-0.32, crect(0.46, 0.52, 0.16)),
        (-0.92, crect(0.56, 0.62, 0.2, oz=-0.04)),
        (-1.42, crect(0.56, 0.62, 0.2, oz=-0.04)),
        (-2.2, crect(0.44, 0.50, 0.16)),
        (-2.42, crect(0.38, 0.44, 0.14)),
    ], by_side({0: {'*': 'red'}, 1: {'*': 'red', 'r': 'serial'}, 2: {'*': 'red'},
                3: {'*': 'frame'}}),
        'frame', 'frame')
    return [drum, arm]


def shin():
    """The shin. Below the knee guard it runs down past the ankle joint into a skirt round the
    ankle (hazard-striped on its sides: a pinch point), so a pitched foot turns inside it."""
    drum = cyl_x('knee_drum', 0.44, 0.84, 8, 'frame', [0, 0, 0])
    knee = loft('knee_guard', 'x', [
        (-0.48, [(-0.3, 0.55), (-0.62, 0.25), (-0.66, -0.45), (-0.42, -0.8), (-0.22, -0.5)]),
        (0.48, [(-0.3, 0.55), (-0.62, 0.25), (-0.66, -0.45), (-0.42, -0.8), (-0.22, -0.5)]),
    ], lambda k, j: 'white', 'white', 'white')
    leg = loft('shin', 'y', [
        (-0.4, crect(0.46, 0.50, 0.16, oz=0.06)),
        (-1.35, crect(0.62, 0.76, 0.22, 0.28, oz=0.16)),
        (-2.08, crect(0.58, 0.72, 0.2, 0.26, oz=0.12)),
        (-2.3, crect(0.56, 0.66, 0.18, 0.24, oz=0.04)),
        (-2.68, crect(0.54, 0.62, 0.16, 0.22, oz=0.0)),
    ], by_side({0: {'*': 'red', 'f': 'white', 'fr': 'white', 'fl': 'white'},
                1: {'*': 'red', 'f': 'white', 'fr': 'white', 'fl': 'white'},
                2: {'*': 'chrome'},
                3: {'*': 'frame', 'r': 'hazard', 'l': 'hazard'}}),
        'frame', 'frame')
    return [drum, knee, leg]


def foot():
    """The foot: a broad ankle drum, the shoe, and an instep plate rising from the shoe into the
    shin's skirt, so a foot pitched toe-up or toe-down still meets the leg."""
    drum = cyl_x('ankle_drum', 0.4, 0.8, 8, 'frame', [0, 0, 0])
    prof = [(0.8, -0.85), (0.86, -0.45), (0.35, -0.15), (-0.45, -0.3), (-1.35, -0.55),
            (-1.7, -0.72), (-1.55, -0.85)]
    # sides: 0 heel, 1 back top, 2 instep, 3 toe top, 4 toe tip, 5 toe under, 6 sole
    smat = ['red', 'red', 'white', 'white', 'red', 'dark', 'dark']
    shoe = loft('shoe', 'x', [(-0.6, prof), (0.6, prof)],
                lambda k, j: smat[j], 'red', 'red')
    tongue = [(-0.86, -0.36), (-0.5, 0.1), (-0.14, 0.18), (-0.02, -0.2)]
    instep = loft('instep', 'x', [(-0.36, tongue), (0.36, tongue)],
                  lambda k, j: 'white' if j == 0 else 'chrome', 'chrome', 'chrome')
    return [drum, shoe, instep]


PARTS = {
    'pelvis': pelvis, 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': hand, 'sword': sword,
    'thigh': thigh, 'shin': shin, 'foot': foot,
}
SIDED = {'pauldron', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot'}


def geometry(part, side, parts=None):
    """The part's nodes, origin at its joint; the right side mirrored in X. `parts`: a table
    like PARTS (an echo's)."""
    nodes = (parts or PARTS)[part]()
    if side == 'r':
        return [{'id': 'mirrored', 'op': 'group', 'children': nodes,
                 'transform': {'scale': [-1, 1, 1]}}]
    return nodes


# ---- the stance -----------------------------------------------------------------------------
# Rotations in degrees (kit order X, Y, Z) at each joint, relative to the parent. The right
# side (-X) leads: right foot forward, the sword in the right hand held out and up in a guard,
# the left fist up in front of the chest. The knees are solved so both soles sit on y = 0.

def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mm(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k]*v[k] for k in range(3)) for i in range(3)]


def rot(e):
    return mm(rz(e[2]), mm(ry(e[1]), rx(e[0])))


PELVIS_DROP = 0.62
STANCE_BASE = {
    'pelvis': [0, -8, 0],
    'torso': [-6, -16, 0],
    'head': [-4, 14, 0],
    'thigh_r': [32, 0, -5], 'thigh_l': [-20, 0, 5],
    'upper_arm_r': [28, 0, -14], 'forearm_r': [42, 0, 4], 'hand_r': [-22, 0, 0],
    'upper_arm_l': [38, 0, 20], 'forearm_l': [78, 0, -6], 'hand_l': [-12, 0, 0],
}


def solve_leg(side, stance, drop):
    """Knee and ankle angles that put this ankle ANKLE above the ground with the sole level."""
    hip_t = [0, ANKLE+THIGH+SHIN-drop, 0]
    pr = rot(stance['pelvis'])
    hx = HIP_X if side == 'l' else -HIP_X
    th = stance[f'thigh_{side}']
    base = mm(pr, rot(th))
    knee = add(hip_t, mv(pr, [hx, 0, 0]))
    knee = add(knee, mv(base, [0, -THIGH, 0]))

    def ankle_y(k):
        return add(knee, mv(mm(base, rx(k)), [0, -SHIN, 0]))[1]
    lo, hi = -150.0, 0.0          # bending the knee (negative X) raises the ankle
    for _ in range(60):
        mid = (lo+hi)/2
        if ankle_y(mid) > ANKLE+0.015:
            lo = mid
        else:
            hi = mid
    k = round((lo+hi)/2, 2)
    px = stance['pelvis'][0]
    return [k, 0, 0], [round(-(px+th[0]+k), 2), 0, round(-th[2], 2)]


def pose(base, drop):
    """A full stance from the hand-set angles: the pauldrons follow the upper arms part way, the
    knees and ankles are solved so both soles sit on the ground."""
    stance = dict(base)
    for s in 'rl':
        stance[f'pauldron_{s}'] = [round(stance[f'upper_arm_{s}'][0]*0.35, 2), 0,
                                   round(stance[f'upper_arm_{s}'][2]*0.5, 2)]
    for s in 'rl':
        stance[f'shin_{s}'], stance[f'foot_{s}'] = solve_leg(s, stance, drop)
    return stance


STANCE = pose(STANCE_BASE, PELVIS_DROP)


def head_frame(stance=None, drop=PELVIS_DROP):
    """The head's middle (1 m above the neck joint) and its rotation, in the stance."""
    stance = stance or STANCE
    p_r = rot(stance['pelvis'])
    p_t = [0, ANKLE+THIGH+SHIN-drop, 0]
    t_r = mm(p_r, rot(stance['torso']))
    t_t = add(p_t, mv(p_r, [0, WAIST, 0]))
    h_r = mm(t_r, rot(stance['head']))
    h_t = add(t_t, mv(t_r, list(NECK)))
    return add(h_t, mv(h_r, [0, 1.0, -0.1])), h_r


def joint(name, part, side, translate, rotate, children=(), parts=None):
    return {'id': name, 'op': 'group',
            'children': geometry(part, side, parts) + list(children),
            'transform': T([round(c, 4) for c in translate], rotate)}


def assemble(stance, parts=None, weapons=None, drop=PELVIS_DROP):
    """The rig as nested groups. weapons: {side: part} held in that hand (default the sword in
    the right), each turned to point out of the fist's thumb side (a normal grip)."""
    weapons = {'r': 'sword'} if weapons is None else weapons

    def st(n):
        return stance.get(n, [0, 0, 0])

    def part(*a, **k):
        return joint(*a, parts=parts, **k)

    def leg(s):
        x = HIP_X if s == 'l' else -HIP_X
        foot_ = part(f'foot_{s}', 'foot', s, [0, -SHIN, 0], st(f'foot_{s}'))
        shin_ = part(f'shin_{s}', 'shin', s, [0, -THIGH, 0], st(f'shin_{s}'), [foot_])
        return part(f'thigh_{s}', 'thigh', s, [x, 0, 0], st(f'thigh_{s}'), [shin_])

    def arm(s):
        x = SHOULDER[0] if s == 'l' else -SHOULDER[0]
        at = [x, SHOULDER[1], SHOULDER[2]]
        kids = []
        if s in weapons:
            kids = [{'id': weapons[s], 'op': 'group',
                     'children': geometry(weapons[s], None, parts),
                     'transform': T([0, GRIP, 0], [-90, 0, 0])}]
        hand_ = part(f'hand_{s}', 'hand', s, [0, -FORE, 0], st(f'hand_{s}'), kids)
        fore = part(f'forearm_{s}', 'forearm', s, [0, -UPPER, 0], st(f'forearm_{s}'), [hand_])
        up = part(f'upper_arm_{s}', 'upper_arm', s, at, st(f'upper_arm_{s}'), [fore])
        pau = part(f'pauldron_{s}', 'pauldron', s, at, st(f'pauldron_{s}'))
        return [pau, up]

    head_ = part('head', 'head', None, NECK, st('head'))
    torso_ = part('torso', 'torso', None, [0, WAIST, 0], st('torso'),
                  [head_] + arm('r') + arm('l'))
    drop = drop if stance else 0.0
    return [part('pelvis', 'pelvis', None, [0, ANKLE+THIGH+SHIN-drop, 0], st('pelvis'),
                 [leg('r'), leg('l'), torso_])]


def recipe(name, nodes, triangles, vertices=2048, materials=None):
    return {
        'format': 'mei-asset', 'version': 1, 'name': name,
        'budget': {'vertices': vertices, 'triangles': triangles},
        'lighting': LIGHTING,
        'verification': POLICY,
        'materials': materials or MATERIALS,
        'nodes': nodes,
    }


def used(nodes):
    """The materials the nodes name, so a part's recipe lists only its own."""
    out = set()

    def walk(n):
        if 'material' in n:
            out.add(n['material'])
        out.update(n.get('face_materials', []))
        out.update(n.get('faces', {}).values()) if isinstance(n.get('faces'), dict) else None
        for c in n.get('children', []):
            walk(c)
    for n in nodes:
        walk(n)
    return out


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1)+'\n')


MOUNT_ROTATE = [-90, 0, 0]     # a weapon's +Y (its blade) out of the fist's thumb side (-Z)


def skeleton(weapons):
    """The rig's joints in the rest pose, parents before children: (id, parent, offset from the
    parent's joint, rest rotation, part builder, side). The same for every mech; `weapons`
    ({side: part}) says which hands hold a weapon part (`weapon_r`, `weapon_l`)."""
    out = [('pelvis', None, [0, ANKLE+THIGH+SHIN, 0], None, 'pelvis', None),
           ('torso', 'pelvis', [0, WAIST, 0], None, 'torso', None),
           ('head', 'torso', list(NECK), None, 'head', None)]
    for s in 'rl':
        x = SHOULDER[0] if s == 'l' else -SHOULDER[0]
        out += [(f'pauldron_{s}', 'torso', [x, SHOULDER[1], SHOULDER[2]], None, 'pauldron', s),
                (f'upper_arm_{s}', 'torso', [x, SHOULDER[1], SHOULDER[2]], None, 'upper_arm', s),
                (f'forearm_{s}', f'upper_arm_{s}', [0, -UPPER, 0], None, 'forearm', s),
                (f'hand_{s}', f'forearm_{s}', [0, -FORE, 0], None, 'hand', s)]
        if s in weapons:
            out.append((f'weapon_{s}', f'hand_{s}', [0, GRIP, 0], MOUNT_ROTATE, weapons[s], None))
    for s in 'rl':
        x = HIP_X if s == 'l' else -HIP_X
        out += [(f'thigh_{s}', 'pelvis', [x, 0, 0], None, 'thigh', s),
                (f'shin_{s}', f'thigh_{s}', [0, -THIGH, 0], None, 'shin', s),
                (f'foot_{s}', f'shin_{s}', [0, -SHIN, 0], None, 'foot', s)]
    return out


def part_name(name, part, side):
    return f'{name}_{part}' + (f'_{side}' if side else '')


def part_facts(recipe_data):
    """Triangles, vertices and bounds (in the part's own frame) of a part recipe, from the Asset
    Kit's compiler (tools/assetkit, standard library only)."""
    tools = Path(__file__).resolve().parents[4]/'tools'
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from assetkit.compiler import compile_recipe
    mesh, _, rep = compile_recipe(recipe_data, budgets='warn')
    return {'triangles': rep['triangles'], 'vertices': rep['vertices'],
            'bounds': {'min': [round(c, 4) for c in rep['bounds']['min']],
                       'max': [round(c, 4) for c in rep['bounds']['max']]}}


def write_rig(folder, name, stance, drop, weapons, part_recipes):
    """NAME.rig.json: the skeleton (README, "Rig (B) -> Animation Kit (A)")."""
    parts = []
    for jid, parent, offset, rest, part, side in skeleton(weapons):
        pname = part_name(name, part, side)
        e = {'id': jid, 'parent': parent, 'offset': [round(c, 4) for c in offset]}
        if rest:
            e['rotate'] = rest
        e['recipe'] = f'parts/{pname}.asset.json'
        e['asset'] = f'ASSET_{pname.upper()}'
        e.update(part_facts(part_recipes[pname]))
        parts.append(e)
    mounts = []
    for s in 'rl':
        mounts.append({'id': f'weapon_{s}', 'parent': f'hand_{s}', 'offset': [0, GRIP, 0],
                       'rotate': MOUNT_ROTATE,
                       'part': f'weapon_{s}' if s in weapons else None,
                       'note': "the grip's middle; the weapon's +Y points out of the fist's thumb "
                               'side, its edge +Z'})
    st = {k: v for k, v in stance.items()}
    rig = {
        'format': 'mei-rig', 'version': 1, 'name': name,
        'units': 'metres; Y up; the mech faces -Z, +X is its left',
        'rotation': 'degrees, applied X then Y then Z, in the parent joint frame (the Asset Kit\'s '
                    'order). Not mirrored between sides: on a hanging limb +X swings it forward; '
                    '+Z swings a left limb out (+X) and a right limb in, so a mirrored pose negates '
                    'Y and Z',
        'root': 'pelvis',
        'root_note': "the root (fight origin) is on the floor under the pelvis; pelvis.offset is "
                     "the rest-pose hip-axle height, a pose lowers it by its 'drop'",
        'parts': parts,
        'mounts': mounts,
        'poses': {'guard': {'drop': round(drop, 4), 'rotate': st,
                            'note': 'the fighting stance the sketch was built in: both soles on y = 0'}},
        'triangles': sum(p['triangles'] for p in parts),
    }
    write(folder/f'{name}.rig.json', rig)
    return rig


def write_mech(folder, name, stance, drop, parts, sided, weapons, materials, budget=1800):
    """The assembled stance, the rest pose, each part alone (parts/NAME_PART[_SIDE]) and the rig
    (NAME.rig.json)."""
    write(folder/f'{name}.asset.json',
          recipe(name, assemble(stance, parts, weapons, drop), budget, materials=materials))
    # the rest pose (every joint at 0), to check the parts line up and the standing height
    write(folder/f'{name}_rest.asset.json',
          recipe(f'{name}_rest', assemble({}, parts, weapons, drop), budget,
                 materials=materials))
    written = {}
    for part in parts:
        for side in (('l', 'r') if part in sided else (None,)):
            pname = part_name(name, part, side)
            nodes = geometry(part, side, parts)
            r = recipe(pname, nodes, 400, 512)
            r['materials'] = {k: v for k, v in materials.items() if k in used(nodes)}
            write(folder/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    # parts no longer made (a renamed part) must not linger for the pack to pick up
    for p in (folder/'parts').glob(f'{name}_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    return write_rig(folder, name, stance, drop, weapons, written)


def camera_set(stance=None, drop=PELVIS_DROP, head_dist=5.2, head_views=None):
    """Side views at game distance and nearer, quarters, and close-ups framed on the head."""
    # Side views: the console's 60-degree vertical field of view gives 120 * 1.732 / d pixels a
    # unit at distance d, so 31 m puts the 12 m mech at about 80 px of the 240.
    mid_z = -2.0
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, 5.8, mid_z], 'target': [0, 5.8, mid_z]},
        {'name': 'side_facing_left', 'eye': [31.2, 5.8, mid_z], 'target': [0, 5.8, mid_z]},
        {'name': 'side_right_near', 'eye': [-17.0, 6.2, mid_z], 'target': [0, 6.2, mid_z]},
        {'name': 'side_left_near', 'eye': [17.0, 6.2, mid_z], 'target': [0, 6.2, mid_z]},
        {'name': 'front_quarter', 'eye': [-12.0, 9.0, -16.0], 'target': [0, 6.0, -1.5]},
        {'name': 'back_quarter', 'eye': [12.0, 9.0, 14.0], 'target': [0, 6.0, 0.0]},
        {'name': 'back_close', 'eye': [-7.5, 10.0, 8.5], 'target': [0, 7.8, 1.2]},
    ]
    # head close-ups, framed on the head where the stance puts it: front, both sides, a quarter
    hc, hr = head_frame(stance, drop)
    views = head_views or (('head_front', [0, 0.15, -1]), ('head_side_right', [-1, 0.1, 0]),
                           ('head_side_left', [1, 0.1, 0]),
                           ('head_three_quarter', [-0.7, 0.3, -0.75]))
    for name, d in views:
        dv = mv(hr, d)
        ln = math.sqrt(dot(dv, dv))
        eye = add(hc, mul(dv, head_dist/ln))
        cams.append({'name': name, 'eye': [round(c, 3) for c in eye],
                     'target': [round(c, 3) for c in hc]})
    return cams


# ---- the flex check: every joint bent far ---------------------------------------------------
# Not a move: a pose that puts each joint near the end of its travel, the knee deep, one foot
# toe-down and one toe-up, one arm overhead, an elbow and a wrist folded, the waist bent and
# turned, so its preview shows whether the joints stay whole. On a foot +X lifts the toe.

FLEX_DROP = 1.7
FLEX_BASE = {
    'pelvis': [10, 0, 0], 'torso': [22, 28, -6], 'head': [-26, -24, 0],
    'upper_arm_r': [165, 0, -12], 'forearm_r': [70, 0, 0], 'hand_r': [-55, 0, 0],
    'upper_arm_l': [-45, 0, 34], 'forearm_l': [135, 0, 0], 'hand_l': [55, 0, 20],
    'thigh_r': [95, 0, -4], 'shin_r': [-125, 0, 0], 'foot_r': [-38, 0, 0],
    'thigh_l': [-28, 0, 6], 'shin_l': [-70, 0, 0], 'foot_l': [42, 0, 0],
}


def flex_pose(base=FLEX_BASE):
    st = dict(base)
    for sd in 'rl':
        st[f'pauldron_{sd}'] = [round(st[f'upper_arm_{sd}'][0]*0.35, 2), 0,
                                round(st[f'upper_arm_{sd}'][2]*0.5, 2)]
    return st


def world_frames(stance, drop, weapons):
    """{joint id: (rotation, position)} in the asset's frame for a stance."""
    out = {}
    for jid, parent, offset, rest, _, _ in skeleton(weapons):
        r = rot(stance.get(jid, [0, 0, 0]) if not rest else rest)
        if parent is None:
            out[jid] = (r, [offset[0], offset[1]-drop, offset[2]])
        else:
            pr, pt = out[parent]
            out[jid] = (mm(pr, r), add(pt, mv(pr, offset)))
    return out


def flex_cameras(stance, drop, weapons):
    """Close views of the joints that bend furthest in the flex pose, from the side and quarter."""
    fr = world_frames(stance, drop, weapons)
    cams = [
        {'name': 'flex_side_right', 'eye': [-17.0, 5.2, -1.0], 'target': [0, 5.2, -1.0]},
        {'name': 'flex_side_left', 'eye': [17.0, 5.2, -1.0], 'target': [0, 5.2, -1.0]},
        {'name': 'flex_front_quarter', 'eye': [-11.0, 7.0, -13.0], 'target': [0, 5.0, -1.0]},
    ]
    for jid, d, dist in (('foot_r', [-1, 0.3, -0.2], 4.2), ('foot_l', [1, 0.3, 0.1], 4.2),
                         ('shin_r', [-1, 0.2, 0.3], 4.5), ('shin_l', [1, 0.2, -0.2], 4.5),
                         ('forearm_l', [1, 0.3, -0.3], 4.0), ('hand_r', [-1, 0.2, -0.4], 3.6),
                         ('hand_l', [0.8, 0.3, -0.8], 3.4), ('torso', [-1, 0.2, -0.6], 6.0),
                         ('upper_arm_r', [-1, 0.0, -0.3], 4.5)):
        _, p = fr[jid]
        ln = math.sqrt(dot(d, d))
        cams.append({'name': f'flex_{jid}', 'eye': [round(p[k]+d[k]*dist/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in p]})
    return cams


def grip_cameras(stance, drop, weapons):
    """Close-ups of each hand in the stance (the grip), from outside and the front quarter."""
    fr = world_frames(stance, drop, weapons)
    cams = []
    for sd, sx in (('r', -1), ('l', 1)):
        _, p = fr[f'hand_{sd}']
        r, _ = fr[f'hand_{sd}']
        c = add(p, mv(r, [0, GRIP, 0]))
        for name, d in (('out', [sx, 0.15, 0]), ('front', [sx*0.5, 0.3, -1])):
            ln = math.sqrt(dot(d, d))
            cams.append({'name': f'grip_{sd}_{name}', 'eye': [round(c[k]+d[k]*4.0/ln, 3) for k in range(3)],
                         'target': [round(v, 3) for v in c]})
    return cams


def write_flex(folder, name, parts, weapons, materials, budget=1800):
    st = flex_pose()
    write(folder/f'{name}_flex.asset.json',
          recipe(f'{name}_flex', assemble(st, parts, weapons, FLEX_DROP), budget,
                 materials=materials))
    write(folder/'cameras_flex.json', flex_cameras(st, FLEX_DROP, weapons))


def write_emblem(path, shapes):
    P.write_png(path, P.render(shapes, 256, 256, None, ss=4))


def main():
    weapons = {'r': 'sword'}
    write_mech(HERE, 'hero', STANCE, PELVIS_DROP, PARTS, SIDED, weapons, MATERIALS)
    write(HERE/'cameras.json', camera_set() + grip_cameras(STANCE, PELVIS_DROP, weapons))
    write_flex(HERE, 'hero', PARTS, weapons, MATERIALS)
    write_emblem(HERE/'momentum_emblem.png', P.emblem_momentum())


if __name__ == '__main__':
    main()
