#!/usr/bin/env python3
"""Mech Expo 2000: Tank (Heartland Atomic Company), the grappler.

Heartland are the atomic era's veterans, family-run and blue-collar, keeping old reactors alive
with salvage and patches (the pitch, Part 2). Tank is the only mech allowed wear (STYLE.md):
faded forest green, primer-grey replacement panels, welding seams, bolted-on cooling and a green
reactor glow through the gaps. Short and wide, on two tread units, with arms bigger than its
legs: it throws people.

It is built on the cart's one skeleton (anim.akr's enum Part), so the Animation Kit and the
runtime need nothing new; the parts mean different things here:

  pelvis        the lower hull between the treads, and the hip axle across it
  torso         the barrel chest, the reactor vessel on the back, two exhaust stacks
  head          a small truck-cab head sunk between the shoulders: two round headlamp eyes,
                a radiator grille for a mouth
  pauldron_*    the shoulder domes (Heartland's mark on the outside)
  upper_arm_*   the shoulder drum and a short, thick arm with a hydraulic ram
  forearm_*     the huge forearms, a cooling pack bolted on the outside of each
  hand_*        the clamp fists (the weapon mounts are empty: Tank fights with its hands)
  thigh_*       the suspension struts from the hip axle down to the treads (short)
  shin_*        the tread units: the track, the road wheels, the armour skirt; the joint at
                the top is the suspension pivot, so the tread rocks fore and aft
  foot_*        the drive sprockets at the back of each tread: spin them (about X) for the glide

The joints are Tank's own (the rig's offsets), not the Hero's, but the part ids, their order
and their parents are the same. Helpers (the loft builder, the writers) come from
../hero/make_hero.py.

Writes, beside this script: tank.asset.json (assembled, in its guard stance), tank_rest.asset.json
(rest pose), tank_flex.asset.json (every joint at the end of its range, for checking; not
packed), parts/tank_*.asset.json (each part alone, its origin at its joint), tank.rig.json,
cameras.json, cameras_flex.json and heartland_emblem.png (the mark for the menus).
Run from anywhere: python3 carts/mechexpo/models/tank/make_tank.py (standard library only).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'hero'))
import make_hero as H  # noqa: E402
import mxpaint as P  # noqa: E402

from make_hero import loft, crect, by_side, box, cyl_x, T  # noqa: E402

# ---- paint (STYLE.md: Heartland is faded forest green with primer grey) ---------------------

GREEN, GREEN_DK, PRIMER = '#5b7350', '#3f5238', '#9d9c92'
GUN, DARK, WELD = '#4d5153', '#232528', '#c2ad7e'
HAZ_Y, HAZ_K = '#d4ad40', '#2b2a25'
CREAM = '#e6dfc4'

# glyphs the serial plate needs that mxpaint's font lacks (added here, not there)
P.FONT.setdefault('H', ['10001', '10001', '10001', '11111', '10001', '10001', '10001'])
P.FONT.setdefault('A', ['01110', '10001', '10001', '11111', '10001', '10001', '10001'])
P.FONT.setdefault('5', ['11111', '10000', '11110', '00001', '00001', '10001', '01110'])


def orbit(colour, c, rx, ry, w, n=28):
    """An ellipse's outline, w thick, as n quads."""
    out = []
    for k in range(n):
        a0, a1 = 2*math.pi*k/n, 2*math.pi*(k+1)/n
        q = [(c[0]+(rx+w/2)*math.cos(a0), c[1]+(ry+w/2)*math.sin(a0)),
             (c[0]+(rx+w/2)*math.cos(a1), c[1]+(ry+w/2)*math.sin(a1)),
             (c[0]+(rx-w/2)*math.cos(a1), c[1]+(ry-w/2)*math.sin(a1)),
             (c[0]+(rx-w/2)*math.cos(a0), c[1]+(ry-w/2)*math.sin(a0))]
        out.append(('poly', colour, q))
    return out


def emblem_heartland(green=GREEN, cream=CREAM, dark=GREEN_DK, glow='#8cff6e'):
    """Heartland Atomic Company: a cream heart on a green roundel, two orbits round it and a
    glowing nucleus in the middle: the homestead and the atom."""
    s = [('disc', cream, (0.5, 0.5), 0.5), ('disc', green, (0.5, 0.5), 0.44)]
    # the heart: two lobes and a point
    s += [('disc', cream, (0.38, 0.42), 0.15), ('disc', cream, (0.62, 0.42), 0.15),
          ('poly', cream, [(0.235, 0.47), (0.765, 0.47), (0.5, 0.80)])]
    # two orbits: ellipses drawn as strips of quads (scaled() would round a squeezed ring)
    for rx, ry in ((0.34, 0.13), (0.13, 0.34)):
        s += orbit(dark, (0.5, 0.52), rx, ry, 0.035)
    s += [('disc', glow, (0.5, 0.52), 0.075)]
    return s


def stripes(colors, w=8, h=8, on=3):
    """A tile of horizontal bars (u along, v across): `on` rows of the second colour in each h."""
    return {'texels': [''.join('1' if j < on else '0' for _ in range(w)) for j in range(h)],
            'colors': list(colors)}


MATERIALS = {
    'green':    {'color': GREEN},
    'green_dk': {'color': GREEN_DK},             # the second green: colour blocking
    'primer':   {'color': PRIMER},               # replacement panels
    'gun':      {'color': GUN},                  # the neutral metal: joints, frame
    'dark':     {'color': DARK},                 # rubber, the grille's depth, soles
    'weld':     {'color': WELD},                 # welding seams
    'glow':     {'color': '#8cff6e', 'class': 'emissive'},   # the reactor, seen through the gaps
    'emblem':   {'color': GREEN, 'texture': {**H.emblem_texture(emblem_heartland(), GREEN),
                                             'projection': 'fit'}},
    'serial':   {'color': PRIMER, 'texture': {**P.serial_plate('HA-57', PRIMER, DARK),
                                              'projection': 'fit'}},
    'hazard':   {'color': HAZ_Y, 'texture': {**P.hazard([HAZ_Y, HAZ_K]),
                                             'projection': 'box', 'scale': [0.32, 0.32]}},
    # the track's links, and the slats of the cooling packs and the grille
    'track':    {'color': DARK, 'texture': {**stripes([DARK, GUN], on=3),
                                            'projection': 'box', 'scale': [0.4, 0.4]}},
    'slats':    {'color': GUN, 'texture': {**stripes([GUN, DARK], on=4),
                                           'projection': 'box', 'scale': [0.22, 0.22]}},
}

# ---- the rig: Tank's joints (rest pose, in the parent's frame) ------------------------------

HIP_Y = 3.3             # the hip axle above the floor
HIP_X = 1.55            # the struts (and the treads under them) either side
STRUT = 0.95            # hip to the tread's pivot
SPROCKET = (0.0, -1.45, 1.75)  # the pivot to the drive sprocket's axle (at the back)
WAIST = 0.55
SHOULDER = (2.85, 3.55, 0.1)
NECK = (0.0, 4.05, -0.5)
UPPER, FORE = 2.2, 2.3
GRIP = -0.72            # wrist to the middle of the fist (the empty weapon mount)
MOUNT_ROTATE = H.MOUNT_ROTATE

# What each part is and how far its joint should turn (degrees, the kit's X, Y, Z; the rig's
# sense). Written into the rig for the animator (MOVES.md, "For the animator").
RANGES = {
    'pelvis':      ('the lower hull; the hip axle', 'x -10..10 (keep the treads flat: pitch the torso instead), y -30..30, z -6..6'),
    'torso':       ('the barrel chest and the reactor', 'x -40..25, y -60..60, z -15..15'),
    'head':        ('the cab head, sunk in the shoulders', 'x -20..25, y -45..45, z -10..10'),
    'pauldron':    ('the shoulder dome; follows the upper arm part way', 'about 0.35 of the upper arm\'s x and 0.5 of its z'),
    'upper_arm':   ('the shoulder drum and the arm', 'x -60..190, y -40..40, z: out -100..in 25 (sign by side)'),
    'forearm':     ('the big forearm', 'x 0..140 (forward only: the elbow), y -30..30'),
    'hand':        ('the clamp fist', 'x -70..70, y -40..40, z -35..35'),
    'thigh':       ('the suspension strut', 'x -15..15, z -8..8 (small: it carries the tread)'),
    'shin':        ('the tread unit; pivot at its top', 'x -14..14 (rock fore and aft), z -6..6; the track must stay on the floor in ground moves'),
    'foot':        ('the drive sprocket', 'x any (spins: about 4 degrees a frame in walk_f, -3.3 in walk_b, 30 in the Clinch and the Bulldozer, 55 in the super\'s dash), y and z 0'),
}

# ---- the parts (left / centre, origin at the joint) -----------------------------------------


def pelvis():
    """The lower hull between the treads: a sloped glacis at the front (hazard-striped lip),
    the hip axle across it."""
    hull = loft('hull', 'y', [
        (-1.85, crect(0.78, 1.25, 0.35, 0.2)),
        (-0.6, crect(0.9, 1.75, 0.55, 0.3)),
        (0.45, crect(0.85, 1.5, 0.45, 0.3, oz=0.05)),
    ], by_side({0: {'*': 'green_dk', 'f': 'hazard', 'fr': 'green_dk', 'fl': 'green_dk'},
                1: {'*': 'green', 'f': 'green', 'b': 'gun'}}),
        'gun', 'gun')
    axle = cyl_x('hip_axle', 0.42, 2*HIP_X+0.5, 8, 'gun', [0, 0, 0])
    return [hull, axle]


def thigh():
    """The suspension strut: a short arm from the hip axle down to the tread, a coil-spring
    damper in front of it."""
    arm = box('strut', [0.55, 1.25, 0.8], 'gun', [0, -0.45, 0.1])
    damper = {'id': 'damper', 'op': 'cylinder', 'radius': 0.2, 'height': 0.9, 'segments': 6,
              'material': 'primer', 'transform': T([0.0, -0.5, -0.55], [-8, 0, 0])}
    return [arm, damper]


TRACK = [(-2.72, -1.4), (-2.4, -0.62), (2.2, -0.62), (2.55, -0.95), (2.68, -1.5), (2.45, -2.05),
         (1.95, -2.35), (-2.0, -2.35), (-2.55, -1.95)]


def shin():
    """The tread unit. The track runs round it (its band textured with links); three road
    wheels and the front idler show on the outside under an armour skirt; the skirt carries the
    serial plate and a primer-grey patch, with a weld seam along it. The drive sprocket (the
    foot) sits at the back, outside the track."""
    track = loft('track', 'x', [(-0.6, TRACK), (0.6, TRACK)],
                 lambda k, j: 'track', 'gun', 'gun')
    wheels = []
    for n, (z, y, r) in enumerate(((-2.12, -1.45, 0.48), (-1.05, -1.85, 0.42), (0.0, -1.85, 0.42),
                                   (1.0, -1.85, 0.42))):
        wheels.append(cyl_x(f'wheel{n}', r, 0.2, 6, 'gun', [0.62, y, z],
                            faces={'top': 'dark', 'bottom': 'dark'}))
    skirt = box('skirt', [0.14, 0.78, 4.3], 'green', [0.73, -0.98, -0.5],
                faces={'right': 'green', 'left': 'green_dk', 'top': 'green_dk'})
    plate = box('serial_plate', [0.06, 0.42, 1.0], 'serial', [0.82, -0.95, -1.2],
                faces={'right': 'serial', 'left': 'primer', 'top': 'primer', 'bottom': 'primer',
                       'front': 'primer', 'back': 'primer'})
    patch = box('patch', [0.06, 0.6, 1.1], 'primer', [0.825, -0.93, 0.2])
    seam = box('seam', [0.07, 0.07, 4.2], 'weld', [0.81, -0.61, -0.5])
    # the pivot block on top of the track, where the strut meets it
    mount = box('pivot', [0.62, 0.42, 0.9], 'gun', [0, -0.35, 0])
    return [track] + wheels + [skirt, plate, patch, seam, mount]


def foot():
    """The drive sprocket: a toothed wheel (an octagon) and a cross of spokes on its outside, so
    a spin reads from the side."""
    wheel = cyl_x('sprocket', 0.78, 0.22, 8, 'gun', [0.68, 0, 0],
                  faces={'top': 'green_dk', 'bottom': 'green_dk'})
    spokes = {'id': 'spokes', 'op': 'group', 'children': [
        box('spoke_a', [0.08, 1.3, 0.26], 'primer', [0.81, 0, 0]),
        box('spoke_b', [0.08, 0.26, 1.3], 'primer', [0.815, 0, 0])]}
    return [wheel, spokes]


def torso():
    """The barrel chest: green with a darker band, a primer replacement panel welded on the left
    breast, a green glow through the vent slot under it; on the back the reactor vessel, its
    glowing window band and cooling fins; two exhaust stacks over the shoulders."""
    waist = loft('waist', 'y', [
        (-0.25, crect(0.95, 0.85, 0.3)),
        (0.55, crect(1.15, 0.95, 0.35)),
    ], lambda k, j: 'gun', None, None)
    chest = loft('chest', 'y', [
        (0.35, crect(1.55, 1.2, 0.45, 0.35)),
        (1.5, crect(2.3, 1.55, 0.65, 0.45, oz=-0.1)),
        (2.95, crect(2.45, 1.6, 0.7, 0.45, oz=-0.12)),
        (4.0, crect(2.05, 1.4, 0.55, 0.4, oz=-0.05)),
        (4.55, crect(1.25, 1.0, 0.35, 0.3)),
    ], by_side({0: {'*': 'green_dk'},
                1: {'*': 'green', 'f': 'green', 'b': 'green_dk'},
                2: {'*': 'green', 'fr': 'hazard', 'fl': 'hazard'},
                3: {'*': 'gun', 'f': 'green_dk'}}),
        'gun', 'gun')
    sockets = cyl_x('shoulder_sockets', 0.55, 2*SHOULDER[0]-0.7, 8, 'gun',
                    [0, SHOULDER[1], SHOULDER[2]])
    patch = box('patch', [1.15, 1.0, 0.12], 'primer', [0.95, 2.35, -1.72], [6, 0, 0])
    seam = box('seam', [1.25, 0.08, 0.1], 'weld', [0.95, 2.86, -1.78], [6, 0, 0])
    vent = box('vent', [1.8, 0.24, 0.1], 'glow', [0, 1.45, -1.62], [10, 0, 0])
    reactor = {'id': 'reactor', 'op': 'cylinder', 'radius': 1.05, 'height': 2.6, 'segments': 8,
               'material': 'green_dk', 'faces': {'top': 'gun', 'bottom': 'gun'},
               'transform': T([0, 2.4, 1.65])}
    window = {'id': 'reactor_window', 'op': 'cylinder', 'radius': 1.1, 'height': 0.42,
              'segments': 8, 'material': 'glow', 'caps': False, 'transform': T([0, 2.55, 1.65])}
    fins = {'id': 'fins', 'op': 'group', 'children': [
        box('fin', [0.12, 2.2, 0.75], 'slats', [0.62, 2.35, 2.75], [0, -20, 0])],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    stacks = {'id': 'stacks', 'op': 'group', 'children': [
        {'id': 'stack', 'op': 'cylinder', 'radius': 0.26, 'height': 2.4, 'segments': 6,
         'material': 'gun', 'faces': {'top': 'dark'}, 'transform': T([1.3, 4.6, 1.15], [-8, 0, 0])}],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    return [waist, chest, sockets, patch, seam, vent, reactor, window, fins, stacks]


def head():
    """A truck-cab head, small and low: two round headlamp eyes glowing reactor green under a
    green visor brim, a radiator grille for a mouth, an antenna, a cable at the back."""
    neck = {'id': 'neck', 'op': 'cylinder', 'radius': 0.4, 'height': 0.5, 'segments': 6,
            'material': 'gun', 'transform': T([0, 0.15, 0])}
    cab = loft('cab', 'y', [
        (0.25, crect(0.78, 0.72, 0.22, 0.18)),
        (0.95, crect(0.85, 0.78, 0.25, 0.2)),
        (1.45, crect(0.62, 0.6, 0.2, 0.16, oz=0.05)),
    ], by_side({0: {'*': 'green', 'f': 'gun'}, 1: {'*': 'green'}}), 'gun', 'green_dk')
    lamps = {'id': 'lamps', 'op': 'group', 'children': [
        {'id': 'lamp', 'op': 'cylinder', 'radius': 0.24, 'height': 0.3, 'segments': 8,
         'material': 'gun', 'faces': {'bottom': 'glow'}, 'transform': T([0.38, 0.88, -0.78], [90, 0, 0])}],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    brim = box('brim', [1.75, 0.16, 0.62], 'green_dk', [0, 1.2, -0.62], [-8, 0, 0])
    grille = box('grille', [0.9, 0.36, 0.1], 'slats', [0, 0.47, -0.79],
                 faces={'back': 'slats'})
    antenna = box('antenna', [0.07, 1.1, 0.07], 'gun', [-0.5, 1.85, 0.3], [-12, 0, 0])
    return [neck, cab, lamps, brim, grille, antenna]


def pauldron():
    """The shoulder dome. Its outer side (+X) on the second band is one flat rectangle, so
    Heartland's mark is drawn on it whole; a primer patch on the front."""
    dome = loft('dome', 'y', [
        (1.0, crect(0.55, 0.7, 0.24, 0.2, ox=0.25)),
        (0.45, crect(1.0, 1.15, 0.36, 0.3, ox=0.45)),
        (-0.55, crect(0.95, 1.15, 0.36, 0.3, ox=0.5)),
        (-0.82, crect(0.8, 0.95, 0.28, 0.24, ox=0.5)),
    ], by_side({0: {'*': 'green', 'fr': 'primer', 'f': 'primer'},
                1: {'*': 'green', 'r': 'emblem'}, 2: {'*': 'gun'}}),
        'gun', 'green')
    return [dome]


def upper_arm():
    drum = cyl_x('shoulder_drum', 0.6, 0.9, 8, 'gun', [0, 0, 0])
    arm = loft('arm', 'y', [
        (-0.3, crect(0.42, 0.44, 0.14)),
        (-2.0, crect(0.38, 0.42, 0.12)),
    ], lambda k, j: 'gun', None, 'gun')
    ram = {'id': 'ram', 'op': 'cylinder', 'radius': 0.16, 'height': 1.6, 'segments': 6,
           'material': 'primer', 'transform': T([0.0, -1.1, -0.5])}
    return [drum, arm, ram]


def forearm():
    """The big forearm: wider than the upper arm, green, a hazard band at the wrist, and a
    cooling pack (slats) bolted on the outside."""
    drum = cyl_x('elbow_drum', 0.5, 0.82, 8, 'gun', [0, 0, 0])
    arm = loft('gauntlet', 'y', [
        (-0.2, crect(0.55, 0.58, 0.18)),
        (-1.2, crect(0.86, 0.88, 0.28, oz=-0.04)),
        (-1.95, crect(0.8, 0.82, 0.26, oz=-0.02)),
        (-2.35, crect(0.6, 0.62, 0.2)),
    ], by_side({0: {'*': 'green', 'b': 'green_dk'}, 1: {'*': 'green'},
                2: {'*': 'hazard'}}),
        'gun', 'gun')
    pack = box('cooling_pack', [0.3, 1.15, 1.05], 'slats', [0.95, -1.4, 0.05],
               faces={'top': 'gun', 'bottom': 'gun', 'back': 'gun', 'front': 'gun'})
    return [drum, arm, pack]


def hand():
    """A clamp fist, half again the Hero's: a block of fingers closed round the mount at
    (0, GRIP, 0), an armoured back plate, a thumb in front."""
    wrist = cyl_x('wrist', 0.34, 0.66, 6, 'gun', [0, 0, 0])
    g = GRIP
    sec = [(0.48, g+0.3), (0.5, g-0.2), (0.27, g-0.42), (-0.42, g-0.27), (-0.42, g+0.25),
           (0.03, g+0.4)]
    fist = loft('fist', 'z', [(-0.48, sec), (0.42, [(x*0.94, g+(y-g)*0.94) for x, y in sec])],
                by_side({'*': {'*': 'gun'}}), 'dark', 'gun')
    back = box('back', [0.2, 0.95, 0.72], 'green', [0.56, g/2-0.1, -0.02], [0, 0, 4],
               faces={'left': 'gun'})
    thumb = box('thumb', [0.3, 0.26, 0.48], 'green_dk', [-0.24, g+0.33, -0.4], [0, 0, -18])
    return [wrist, fist, back, thumb]


PARTS = {
    'pelvis': pelvis, 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': upper_arm, 'forearm': forearm, 'hand': hand,
    'thigh': thigh, 'shin': shin, 'foot': foot,
}
SIDED = {'pauldron', 'upper_arm', 'forearm', 'hand', 'thigh', 'shin', 'foot'}
WEAPONS = {}            # the mounts stay empty


def geometry(part, side):
    return H.geometry(part, side, PARTS)


# ---- the skeleton and the assembled poses ----------------------------------------------------

def skeleton():
    """(id, parent, offset, rest rotation, part, side), parents first: the Hero's ids and
    order (make_hero.skeleton) with Tank's offsets."""
    out = [('pelvis', None, [0, HIP_Y, 0], None, 'pelvis', None),
           ('torso', 'pelvis', [0, WAIST, 0], None, 'torso', None),
           ('head', 'torso', list(NECK), None, 'head', None)]
    for s in 'rl':
        x = SHOULDER[0] if s == 'l' else -SHOULDER[0]
        out += [(f'pauldron_{s}', 'torso', [x, SHOULDER[1], SHOULDER[2]], None, 'pauldron', s),
                (f'upper_arm_{s}', 'torso', [x, SHOULDER[1], SHOULDER[2]], None, 'upper_arm', s),
                (f'forearm_{s}', f'upper_arm_{s}', [0, -UPPER, 0], None, 'forearm', s),
                (f'hand_{s}', f'forearm_{s}', [0, -FORE, 0], None, 'hand', s)]
    for s in 'rl':
        x = HIP_X if s == 'l' else -HIP_X
        out += [(f'thigh_{s}', 'pelvis', [x, 0, 0], None, 'thigh', s),
                (f'shin_{s}', f'thigh_{s}', [0, -STRUT, 0], None, 'shin', s),
                (f'foot_{s}', f'shin_{s}', list(SPROCKET), None, 'foot', s)]
    return out


def assemble(stance, drop=0.0):
    """The rig as nested groups, posed."""
    sk = skeleton()
    kids = {}
    for jid, parent, *_ in sk:
        kids.setdefault(parent, []).append(jid)

    def node(jid):
        _, parent, offset, _, part, side = next(e for e in sk if e[0] == jid)
        t = list(offset)
        if parent is None:
            t[1] -= drop
        return {'id': jid, 'op': 'group',
                'children': geometry(part, side) + [node(k) for k in kids.get(jid, [])],
                'transform': T([round(c, 4) for c in t], stance.get(jid))}
    return [node('pelvis')]


def write_rig(stance, drop, part_recipes):
    parts = []
    for jid, parent, offset, rest, part, side in skeleton():
        pname = H.part_name('tank', part, side)
        e = {'id': jid, 'parent': parent, 'offset': [round(c, 4) for c in offset]}
        if rest:
            e['rotate'] = rest
        e['recipe'] = f'parts/{pname}.asset.json'
        e['asset'] = f'ASSET_{pname.upper()}'
        e.update(H.part_facts(part_recipes[pname]))
        role, rng = RANGES[part]
        e['role'] = role
        e['range'] = rng
        parts.append(e)
    mounts = [{'id': f'weapon_{s}', 'parent': f'hand_{s}', 'offset': [0, GRIP, 0],
               'rotate': MOUNT_ROTATE, 'part': None,
               'note': "empty: the middle of the clamp fist (a held mech's shoulder goes here)"}
              for s in 'rl']
    rig = {
        'format': 'mei-rig', 'version': 1, 'name': 'tank',
        'units': 'metres; Y up; the mech faces -Z, +X is its left',
        'rotation': 'degrees, applied X then Y then Z, in the parent joint frame (the Asset Kit\'s '
                    'order). Not mirrored between sides: on a hanging limb +X swings it forward; '
                    '+Z swings a left limb out (+X) and a right limb in, so a mirrored pose negates '
                    'Y and Z',
        'root': 'pelvis',
        'root_note': "the root (fight origin) is on the floor under the pelvis; pelvis.offset is "
                     "the rest-pose hip-axle height. Tank has no knees: the treads stay on the "
                     "floor, so a pose's 'drop' is 0 and the body dips by pitching the torso",
        'parts': parts,
        'mounts': mounts,
        'poses': {'guard': {'drop': round(drop, 4), 'rotate': {k: v for k, v in stance.items()},
                            'note': 'the grappler\'s guard: hunched forward, the big fists low and out in '
                                    'front, both treads flat on y = 0'}},
        'triangles': sum(p['triangles'] for p in parts),
    }
    H.write(HERE/'tank.rig.json', rig)
    return rig


def write_mech(stance, drop, budget=1800):
    H.write(HERE/'tank.asset.json', H.recipe('tank', assemble(stance, drop), budget,
                                             materials=MATERIALS))
    H.write(HERE/'tank_rest.asset.json', H.recipe('tank_rest', assemble({}), budget,
                                                  materials=MATERIALS))
    written = {}
    for part in PARTS:
        for side in (('l', 'r') if part in SIDED else (None,)):
            pname = H.part_name('tank', part, side)
            nodes = geometry(part, side)
            r = H.recipe(pname, nodes, 400, 512)
            r['materials'] = {k: v for k, v in MATERIALS.items() if k in H.used(nodes)}
            H.write(HERE/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    for p in (HERE/'parts').glob('tank_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    return write_rig(stance, drop, written)


# ---- the guard stance -----------------------------------------------------------------------
# Hunched forward over the treads, the head up, both fists low and out in front like a wrestler
# about to tie up. The treads stay flat (no drop).

DROP = 0.0
STANCE_BASE = {
    'torso': [-10, -14, 0],
    'head': [12, 10, 0],
    'upper_arm_r': [24, 0, -16], 'forearm_r': [76, 0, 0], 'hand_r': [-14, 0, 0],
    'upper_arm_l': [18, 0, 18], 'forearm_l': [82, 0, 0], 'hand_l': [-18, 0, 0],
}


def follow_pauldrons(st):
    st = dict(st)
    for s in 'rl':
        ua = st.get(f'upper_arm_{s}', [0, 0, 0])
        st[f'pauldron_{s}'] = [round(ua[0]*0.35, 2), 0, round(ua[2]*0.5, 2)]
    return st


STANCE = follow_pauldrons(STANCE_BASE)

# ---- the flex check: each joint near the end of its range -------------------------------------

FLEX = follow_pauldrons({
    'pelvis': [0, 20, 0], 'torso': [-38, 40, -10], 'head': [22, -35, 0],
    'upper_arm_r': [175, 0, -20], 'forearm_r': [130, 0, 0], 'hand_r': [-60, 0, 0],
    'upper_arm_l': [-50, 0, 90], 'forearm_l': [120, 0, 0], 'hand_l': [60, 0, 30],
    'thigh_r': [14, 0, 0], 'shin_r': [-14, 0, 0], 'foot_r': [45, 0, 0],
    'thigh_l': [-12, 0, 0], 'shin_l': [12, 0, 0], 'foot_l': [-60, 0, 0],
})


def world_frames(stance, drop=0.0):
    out = {}
    for jid, parent, offset, rest, _, _ in skeleton():
        r = H.rot(stance.get(jid, [0, 0, 0]))
        if parent is None:
            out[jid] = (r, [offset[0], offset[1]-drop, offset[2]])
        else:
            pr, pt = out[parent]
            out[jid] = (H.mm(pr, r), H.add(pt, H.mv(pr, offset)))
    return out


def cameras(stance, drop):
    """Side views at game distance (about 80 px tall: the 12 m frame, Tank a little shorter),
    nearer ones, quarters, the head close up, and each fist."""
    mid_z = -1.0
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, 5.2, mid_z], 'target': [0, 5.2, mid_z]},
        {'name': 'side_facing_left', 'eye': [31.2, 5.2, mid_z], 'target': [0, 5.2, mid_z]},
        {'name': 'side_right_near', 'eye': [-17.0, 5.4, mid_z], 'target': [0, 5.4, mid_z]},
        {'name': 'side_left_near', 'eye': [17.0, 5.4, mid_z], 'target': [0, 5.4, mid_z]},
        {'name': 'front_quarter', 'eye': [-12.0, 8.0, -16.0], 'target': [0, 5.0, -1.5]},
        {'name': 'back_quarter', 'eye': [12.0, 8.5, 14.0], 'target': [0, 5.0, 0.0]},
        {'name': 'back_close', 'eye': [-7.5, 9.0, 8.5], 'target': [0, 6.8, 1.2]},
        {'name': 'treads_close', 'eye': [-8.0, 2.2, -4.0], 'target': [-1.5, 1.3, 0.0]},
    ]
    fr = world_frames(stance, drop)
    hr, hp = fr['head']
    hc = H.add(hp, H.mv(hr, [0, 0.85, -0.4]))
    for name, d in (('head_front', [0, 0.15, -1]), ('head_side_right', [-1, 0.1, 0]),
                    ('head_three_quarter', [-0.7, 0.3, -0.75])):
        dv = H.mv(hr, d)
        ln = math.sqrt(H.dot(dv, dv))
        cams.append({'name': name, 'eye': [round(hc[k]+dv[k]*4.0/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in hc]})
    for sd, sx in (('r', -1), ('l', 1)):
        r, p = fr[f'hand_{sd}']
        c = H.add(p, H.mv(r, [0, GRIP, 0]))
        d = [sx, 0.2, -0.6]
        ln = math.sqrt(H.dot(d, d))
        cams.append({'name': f'fist_{sd}', 'eye': [round(c[k]+d[k]*4.5/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    return cams


def flex_cameras():
    fr = world_frames(FLEX)
    cams = [
        {'name': 'flex_side_right', 'eye': [-17.0, 5.0, -1.0], 'target': [0, 5.0, -1.0]},
        {'name': 'flex_side_left', 'eye': [17.0, 5.0, -1.0], 'target': [0, 5.0, -1.0]},
        {'name': 'flex_front_quarter', 'eye': [-11.0, 7.0, -13.0], 'target': [0, 5.0, -1.0]},
    ]
    for jid, d, dist in (('shin_r', [-1, 0.3, -0.2], 6.5), ('shin_l', [1, 0.3, 0.1], 6.5),
                         ('forearm_r', [-1, 0.3, -0.3], 5.0), ('hand_l', [0.8, 0.3, -0.8], 4.5),
                         ('torso', [-1, 0.2, -0.6], 7.0), ('upper_arm_l', [1, 0.0, -0.3], 5.0)):
        _, p = fr[jid]
        ln = math.sqrt(H.dot(d, d))
        cams.append({'name': f'flex_{jid}', 'eye': [round(p[k]+d[k]*dist/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in p]})
    return cams


def main():
    write_mech(STANCE, DROP)
    H.write(HERE/'cameras.json', cameras(STANCE, DROP))
    H.write(HERE/'tank_flex.asset.json', H.recipe('tank_flex', assemble(FLEX), 1800,
                                                  materials=MATERIALS))
    H.write(HERE/'cameras_flex.json', flex_cameras())
    H.write_emblem(HERE/'heartland_emblem.png', emblem_heartland())


if __name__ == '__main__':
    main()
