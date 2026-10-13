#!/usr/bin/env python3
"""Mech Expo 2000: the Twins (Binary Mechanica), the stance mech: two small mechs, or one.

Binary Mechanica is the freshest company at the expo, a high-tech startup whose founding idea is
the two-in-one mech (the pitch, Part 2). Its look is Y2K consumer electronics: pearl-white and
silver plastic, brushed chrome, clear tinted shells over a glow. The company's emblem is a disc
in two halves docking, a 1 on one and a 0 on the other, and the twins are those two digits:

  twin A  "the 1": tall and slim (7.5 m to the top of its fin), long legs, a thin chest seen
          side-on, a tall blade fin on the head; accent cyan, a cyan glow. A vertical glowing
          bar on the chest under a clear shell, a slim upright fusion cell on its back.
  twin B  "the 0": short and stocky (7.0 m), a deep barrel chest, round shoulder domes, short
          thick legs and big feet; accent berry pink (apart from the Hero's red, Umbral's
          violet, Raiko's yellow and Heartland's green), a pink glow. A glowing ring on the
          chest, a round fusion cell (a drum seen side-on as a disc) on its back, round hips.
  twins   the combined form, 12 m: twin A is the upper body (its head, torso and arms, about
          1.6 times twin A's size), twin B the lower (its hips and legs, about 1.5 to 1.76 times),
          each in its own accent. Twin A's legs fold up the back as two fins with thrusters;
          twin B's forearms fold down as the hip skirts and its round cell rides behind the
          hips. Only the combined form has the waist coupling (a chrome collar, a hazard band and
          a white fusion glow), the big shoulder plates (cyan at the front, pink behind, Binary
          Mechanica's mark, a clear fin), a V crest in both accents, and a "10" on the chest
          (two, in binary: the 1 and the 0 together).

All three are built on the cart's one skeleton (anim.akr's enum Part: the Hero's ids, order and
parents), each with its own joint offsets, so the Animation Kit and the runtime need nothing
new. The weapon mounts are empty (the twins fight with their fists). Each rig names its parts'
roles and joint ranges for the animators; the combined rig also has `combined_map`, where each
twin's parts sit in the combined form, so a twin's `combine` can end where the combined form
begins.

Writes, in ../twins/, ../twin_a/ and ../twin_b/ (one folder per body, NAME = twins, twin_a,
twin_b): NAME.asset.json (assembled, in its guard), NAME_rest.asset.json (the rest pose),
NAME_flex.asset.json (every joint bent far, for checking; not packed), parts/NAME_*.asset.json
(each part alone, its origin at its joint), NAME.rig.json, cameras.json, cameras_flex.json and
asset-preview.json (the preview's hangar look); and binary_emblem.png (the mark, for the menus)
here. Helpers (the loft builder, the writers) come from ../hero/make_hero.py.
Run from anywhere: python3 carts/mechexpo/models/twins/make_twins.py (standard library only).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parent
sys.path.insert(0, str(MODELS/'hero'))
import make_hero as H  # noqa: E402
import mxpaint as P  # noqa: E402

loft, crect, by_side, cyl_x, box, T = H.loft, H.crect, H.by_side, H.cyl_x, H.box, H.T

# ---- paint (STYLE.md: Binary Mechanica is white, silver and cyan, in translucent plastic) ----

WHITE, SILVER, FRAME, DARK = '#f2f5f9', '#c3cdd9', '#5b6577', '#22262e'
CYAN, PINK = '#1fc6ee', '#ff4aab'
GLOW, PGLOW, FGLOW = '#a2fbff', '#ffb6e3', '#f4ffff'
HAZ_Y = '#f0c419'


def half_disc(colour, c, r, right, n=10):
    """A half disc as a polygon: the right half (+x in the picture) or the left."""
    a0 = -math.pi/2 if right else math.pi/2
    pts = [(c[0]+r*math.cos(a0+math.pi*k/n), c[1]+r*math.sin(a0+math.pi*k/n)) for k in range(n+1)]
    return ('poly', colour, pts)


def emblem_binary(white='#ffffff', cyan='#30d8f0', silver='#c8d0dc', ink='#2a2c31',
                  one='#3a4458'):
    """Binary Mechanica (as the menus draw it, gen_mechexpo_ui.py's emblem_binary): a disc in
    two halves docking, white and cyan, a 1 on the white half and a 0 on the cyan, in a silver
    ring."""
    return [('disc', silver, (0.5, 0.5), 0.5), ('disc', ink, (0.5, 0.5), 0.41),
            half_disc(white, (0.5, 0.5), 0.35, False), half_disc(cyan, (0.5, 0.5), 0.35, True),
            ('poly', ink, [(0.46, 0.1), (0.54, 0.1), (0.54, 0.9), (0.46, 0.9)]),
            ('poly', one, [(0.29, 0.33), (0.37, 0.33), (0.37, 0.67), (0.29, 0.67)]),
            ('ring', ink, (0.67, 0.5), 0.06, 0.12)]


def stripes_v(colors, w=8, h=8, on=4):
    return {'texels': [''.join('1' if j < on else '0' for _ in range(w)) for j in range(h)],
            'colors': list(colors)}


def mark(field):
    return {'color': field, 'texture': {**H.emblem_texture(
        emblem_binary(white=WHITE, cyan=CYAN, silver=SILVER, ink=DARK), field), 'projection': 'fit'}}


def plate(text, field):
    return {'color': field, 'texture': {**P.serial_plate(text, field, DARK), 'projection': 'fit'}}


MATERIALS = {
    'white':   {'color': WHITE},                 # the pearl-white plastic shells
    'silver':  {'color': SILVER, 'smooth': True},   # brushed chrome
    'frame':   {'color': FRAME},                 # the neutral metal: joints, frame
    'dark':    {'color': DARK},                  # soles, the face's depth
    'cyan':    {'color': CYAN},                  # twin A's accent
    'pink':    {'color': PINK},                  # twin B's accent
    'glow':    {'color': GLOW, 'class': 'emissive'},    # twin A's eyes and core
    'pglow':   {'color': PGLOW, 'class': 'emissive'},   # twin B's eyes and core
    'fglow':   {'color': FGLOW, 'class': 'emissive'},   # the fusion: only when combined
    # clear tinted plastic over a glow (blend half): a few small pieces a body, so they read
    # at 50-80 px and cost little
    'shell':   {'color': '#bfeefc', 'smooth': True, 'blend': 'half'},
    'pshell':  {'color': '#fcc8e6', 'smooth': True, 'blend': 'half'},
    'emblem':  mark(WHITE),
    'emblem_p': mark(PINK),
    'serial_a': plate('BM-21', WHITE),
    'serial_b': plate('BM-20', WHITE),
    'serial': plate('BM-2X', WHITE),
    'hazard':  {'color': HAZ_Y, 'texture': {**P.hazard([HAZ_Y, DARK]),
                                            'projection': 'box', 'scale': [0.32, 0.32]}},
    'vents':   {'color': SILVER, 'texture': {**stripes_v([SILVER, FRAME]),
                                             'projection': 'box', 'scale': [0.2, 0.2]}},
}
LOOK = {'background': ['#56647a', '#a4b0be'], 'ground': '#7a8592'}


# ---- helpers ---------------------------------------------------------------------------------
# The twins are small (about 50 px at the camera's widest) and three bodies share the screen in
# the split form, so their sections have six points; the combined form's (FINE) have eight, and
# its drums more segments. A section carries the names of its sides for the paint tables.

FINE = False


class fine:
    """`with fine():` builds the combined form's parts: rounder sections, smoother drums."""

    def __enter__(self):
        global FINE
        self.was, FINE = FINE, True

    def __exit__(self, *a):
        global FINE
        FINE = self.was


def SEG(n=6):
    return n+2 if FINE else n


class Sec(list):
    names = H.SIDES


def sec(pts, names):
    s = Sec(pts)
    s.names = names
    return s


def sec_a(w, d, cf, ox=0.0, oz=0.0):
    """Twin A's section: crisp, the front corners cut, the back square (sides fr r b l fl f);
    in the combined form the back corners are cut too (crect's eight)."""
    if FINE:
        return sec(crect(w, d, cf, 0.6*cf, ox, oz), H.SIDES)
    pts = [(w-cf, -d), (w, -d+cf), (w, d), (-w, d), (-w, -d+cf), (-w+cf, -d)]
    return sec([(x+ox, z+oz) for x, z in pts], ['fr', 'r', 'b', 'l', 'fl', 'f'])


def sec_b(w, d, ox=0.0, oz=0.0):
    """Twin B's section: round, a hexagon with flat front and back (sides f fr br b bl fl);
    in the combined form an octagon."""
    if FINE:
        c = 0.55*min(w, d)
        return sec(crect(w, d, c, c, ox, oz), H.SIDES)
    pts = [(0.5*w, -d), (w, 0.0), (0.5*w, d), (-0.5*w, d), (-w, 0.0), (-0.5*w, -d)]
    return sec([(x+ox, z+oz) for x, z in pts], ['fr', 'br', 'b', 'bl', 'fl', 'f'])


def L(id_, axis, secs, table, cap0, cap1):
    """loft() with paint by side name: table {band: {name: material, '*': default}} (bands
    missing use table['*']), or a single material."""
    names = secs[0][1].names if isinstance(secs[0][1], Sec) else H.SIDES

    def mat(k, j):
        if isinstance(table, str):
            return table
        row = table.get(k, table.get('*'))
        return row.get(names[j], row['*'])
    return loft(id_, axis, secs, mat, cap0, cap1)


def cyl_y(id_, r, h, seg, mat, at, faces=None, caps=True, rotate=None):
    n = {'id': id_, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': seg,
         'material': mat, 'transform': T(at, rotate)}
    if faces:
        n['faces'] = faces
    if not caps:
        n['caps'] = False
    return n


def drum(id_, r, length, mat, at, faces=None, caps=True):
    """A drum along X (a joint), six segments (eight in the combined form)."""
    n = cyl_x(id_, r, length, SEG(), mat, at, faces)
    if not caps:
        n['caps'] = False
    return n


def cyl_z(id_, r, h, seg, mat, at, faces=None):
    """A drum along Z: 'bottom' faces the front (-Z), 'top' the back."""
    n = {'id': id_, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': seg,
         'material': mat, 'transform': T(at, [90, 0, 0])}
    if faces:
        n['faces'] = faces
    return n


def mirror(id_, children):
    return {'id': id_, 'op': 'group', 'children': children,
            'modifiers': [{'op': 'mirror', 'axis': 'x'}]}


def group(id_, children, translate=None, rotate=None, scale=None):
    return {'id': id_, 'op': 'group', 'children': children,
            'transform': T(translate, rotate, scale)}


class Dims:
    """A body's joints (rest pose, in the parent's frame), as make_hero's module constants."""

    def __init__(self, **k):
        self.__dict__.update(k)

    @property
    def hip_y(self):
        return self.ankle+self.shin+self.thigh


def fist(k, acc):
    """A fist closed round the (empty) weapon mount at (0, -0.42 k, 0): the Hero's fist outline
    (make_hero.hand), its outer side in the accent; in the combined form an armoured back plate
    and a thumb too."""
    g = -0.42*k
    wrist = drum('wrist', 0.2*k, 0.44*k, 'silver', [0, 0, 0], caps=False)
    s = [(0.31, 0.2), (0.33, -0.12), (0.17, -0.27), (-0.27, -0.17), (-0.27, 0.16), (0.02, 0.26)]
    s0 = [(x*k, g+y*k) for x, y in s]
    s1 = [(x*k*0.94, g+y*k*0.94) for x, y in s]
    out = [wrist, loft('fist', 'z', [(-0.29*k, s0), (0.25*k, s1)],
                       lambda b, j: acc if j == 0 else 'frame', 'dark', 'frame')]
    if FINE:
        out += [box('back', [0.15*k, 0.6*k, 0.42*k], 'white', [0.37*k, g/2-0.04*k, -0.01*k],
                    [0, 0, 4], faces={'left': 'frame'}),
                box('thumb', [0.2*k, 0.17*k, 0.3*k], acc, [-0.16*k, g+0.2*k, -0.24*k], [0, 0, -18])]
    return out


def boot(ankle, sx, sz, toe, top, heel='white'):
    """A foot: the ankle drum and the shoe, a profile along X (the Hero's, simplified), the
    sole at -ankle. sx, sz: half width, length scale; toe: the toe cap's material, top: the
    instep's."""
    k = ankle/0.85
    prof = [(0.8, -0.85), (0.86, -0.45), (0.35, -0.12), (-1.35, -0.52), (-1.62, -0.85)]
    prof = [(z*sz, y*k) for z, y in prof]
    # sides: 0 heel, 1 back top, 2 instep, 3 toe, 4 sole
    smat = [heel, heel, top, toe, 'dark']
    shoe = loft('shoe', 'x', [(-sx, prof), (sx, prof)], lambda b, j: smat[j], heel, heel)
    ankle_drum = drum('ankle_drum', 0.4*k, 0.8*k*sx/0.6, 'frame', [0, 0, 0])
    return [ankle_drum, shoe]


# ---- twin A, "the 1": tall and slim, cyan ----------------------------------------------------

A = Dims(ankle=0.476, shin=1.62, thigh=1.55, hip_x=0.52, waist=0.42, shoulder=(1.05, 1.78, 0.02),
         neck=(0.0, 2.1, -0.04), upper=1.3, fore=1.22, hand=0.62)
A.grip = round(-0.42*A.hand, 4)


def a_pelvis():
    core = L('core', 'y', [
        (0.34, sec_a(0.42, 0.34, 0.12)),
        (0.04, sec_a(0.5, 0.4, 0.15)),
        (-0.5, sec_a(0.2, 0.26, 0.07, oz=-0.04)),
    ], {0: {'*': 'white', 'r': 'cyan', 'l': 'cyan', 'b': 'silver'},
        1: {'*': 'frame', 'f': 'white', 'fr': 'white', 'fl': 'white'}},
        'silver', 'frame')
    axle = drum('hip_axle', 0.17, 2*A.hip_x, 'frame', [0, 0, 0], caps=False)
    return [core, axle]


def a_torso(combined=False):
    """The slim chest: thin seen side-on, a V from the front. Its core is a glowing bar under a
    clear shell (the 1). On the back a slim upright fusion cell (a clear tube round a glow).
    combined: the combined form's torso (drawn 1.9 x 1.65 x 1.65 by the caller): no cell (twin
    A's folded legs ride there), and the chest reads "10": the 1 beside twin B's 0."""
    abdomen = L('abdomen', 'y', [
        (-0.15, sec_a(0.3, 0.27, 0.1)),
        (0.55, sec_a(0.38, 0.32, 0.12)),
    ], 'frame', None, None)
    chest = L('chest', 'y', [
        (0.45, sec_a(0.48, 0.38, 0.14)),
        (1.05, sec_a(0.84, 0.52, 0.24, oz=-0.05)),
        (1.75, sec_a(0.9, 0.55, 0.26, oz=-0.05)),
        (2.2, sec_a(0.48, 0.38, 0.14)),
    ], {0: {'*': 'white', 'fr': 'cyan', 'fl': 'cyan', 'b': 'silver'},
        1: {'*': 'white', 'r': 'cyan', 'l': 'cyan'},
        2: {'*': 'silver'}},
        'frame', 'frame')
    one_x = -0.2 if combined else 0.0
    core = box('core', [0.13, 0.5, 0.1], 'glow', [one_x, 1.32, -0.62])
    shell = box('core_shell', [0.26, 0.64, 0.14], 'shell', [one_x, 1.32, -0.645],
                open_=['front'])
    collar = L('collar', 'y', [
        (2.12, sec_a(0.32, 0.27, 0.1)),
        (2.32, sec_a(0.24, 0.21, 0.08)),
    ], 'white', None, 'frame')
    out = [abdomen, chest, core, shell, collar]
    if combined:
        # twin B's 0 beside the 1: a glowing pink ring round a dark centre
        out += [cyl_z('zero', 0.2, 0.1, 8, 'frame', [0.2, 1.32, -0.6], faces={'bottom': 'pglow'}),
                cyl_z('zero_hole', 0.09, 0.1, 6, 'dark', [0.2, 1.32, -0.63])]
    else:
        out += [box('cell_mount', [0.42, 0.84, 0.3], 'frame', [0, 1.35, 0.5]),
                cyl_y('cell', 0.24, 1.1, 6, 'shell', [0, 1.4, 0.74],
                      faces={'top': 'silver', 'bottom': 'silver'}),
                cyl_y('cell_core', 0.13, 0.9, 6, 'glow', [0, 1.4, 0.74], caps=False)]
    return out


def a_head(combined=False):
    """A tall, narrow helmet, a cyan glow under a clear visor, chrome ear pods and a tall blade
    fin: the 1. combined: the combined form's head (drawn 1.5 times) adds a V crest, one wing
    in each twin's accent."""
    neck = cyl_y('neck', 0.17, 0.36, 6, 'frame', [0, 0.12, 0], caps=False)
    helmet = L('helmet', 'y', [
        (0.15, sec_a(0.25, 0.3, 0.08)),
        (0.38, sec_a(0.32, 0.36, 0.11)),
        (0.64, sec_a(0.34, 0.38, 0.12, oz=-0.01)),
        (0.98, sec_a(0.22, 0.26, 0.07, oz=0.02)),
    ], {0: {'*': 'white', 'f': 'silver', 'fr': 'silver', 'fl': 'silver'},
        1: {'*': 'white', 'f': 'glow', 'fr': 'glow', 'fl': 'glow'},
        2: {'*': 'white', 'b': 'silver'}},
        'frame', 'silver')
    visor = H.chevron('visor', 'shell',
                      [(-0.37, 0.36), (-0.5, 0.42), (-0.48, 0.62), (-0.38, 0.66)],
                      [(-0.31, 0.38), (-0.38, 0.42), (-0.37, 0.6), (-0.31, 0.63)], 0.27)
    fin = [(-0.3, 0.9), (-0.14, 1.42), (0.04, 1.46), (0.16, 0.95)]
    crest = loft('fin', 'x', [(-0.05, fin), (0.05, fin)],
                 lambda k, j: 'cyan' if j == 0 else 'white', 'cyan', 'cyan')
    ears = drum('ears', 0.15, 0.8, 'silver', [0, 0.52, 0.06], faces={'top': 'cyan', 'bottom': 'cyan'})
    out = [neck, helmet, visor, crest, ears]
    if combined:
        # the V: a wing from each temple, swept up and back; the left (+X) cyan, the right pink
        for s, mat in ((1, 'cyan'), (-1, 'pink')):
            out.append({'id': f'wing_{"l" if s > 0 else "r"}', 'op': 'extrude', 'depth': 0.06,
                        'material': mat, 'faces': {'side': 'silver'},
                        'points': [[s*0.3, 0.6], [s*0.3, 0.78], [s*0.82, 1.22], [s*0.56, 0.72]],
                        'transform': {'pivot': [s*0.3, 0.68, 0], 'rotate': [0, s*-26, 0],
                                      'translate': [0, 0, -0.22]}})
    return out


def a_pauldron():
    """A small angular plate; the outer face (the middle band's +X side, flat) carries the mark."""
    pl = L('plate', 'y', [
        (0.42, sec_a(0.24, 0.3, 0.1, ox=0.12)),
        (0.2, sec_a(0.4, 0.44, 0.13, ox=0.21)),
        (-0.28, sec_a(0.4, 0.44, 0.13, ox=0.21)),
        (-0.4, sec_a(0.34, 0.38, 0.11, ox=0.22)),
    ], {0: {'*': 'cyan'}, 1: {'*': 'white', 'r': 'emblem'}, 2: {'*': 'silver'}},
        'frame', 'cyan')
    return [pl]


def a_upper_arm():
    # the drum's ends are under the shoulder plate: no caps
    sh = drum('shoulder_drum', 0.26, 0.4, 'frame', [0, 0, 0], caps=False)
    arm = L('arm', 'y', [
        (-0.16, sec_a(0.17, 0.19, 0.06)),
        (-1.16, sec_a(0.15, 0.17, 0.05)),
    ], 'frame', None, 'frame')
    return [sh, arm]


def a_forearm():
    el = drum('elbow_drum', 0.2, 0.36, 'silver', [0, 0, 0])
    arm = L('gauntlet', 'y', [
        (-0.16, sec_a(0.21, 0.22, 0.07)),
        (-0.66, sec_a(0.28, 0.3, 0.1, oz=0.02)),
        (-1.16, sec_a(0.23, 0.25, 0.07)),
    ], {0: {'*': 'white', 'r': 'cyan', 'f': 'cyan'}, 1: {'*': 'white', 'r': 'cyan'}},
        'white', 'frame')
    g = [(0.12, 0.23), (0.32, 0.09), (0.33, -0.3), (0.17, -0.41)]
    guard = loft('elbow_guard', 'x', [(-0.23, g), (0.23, g)], lambda k, j: 'white', 'white', 'white')
    return [el, arm, guard]


def a_hand():
    return fist(A.hand, 'cyan')


def a_thigh():
    """The thigh: deeper than wide (it is seen side-on); the serial plate on its outer side."""
    hd = drum('hip_drum', 0.26, 0.34, 'silver', [0, 0, 0])
    leg = L('thigh', 'y', [
        (-0.18, sec_a(0.23, 0.27, 0.08)),
        (-0.5, sec_a(0.28, 0.36, 0.1, oz=-0.02)),
        (-1.0, sec_a(0.28, 0.36, 0.1, oz=-0.02)),
        (-1.52, sec_a(0.2, 0.24, 0.07)),
    ], {0: {'*': 'white'}, 1: {'*': 'white', 'f': 'cyan', 'r': 'serial_a'},
        2: {'*': 'white', 'b': 'frame'}},
        'frame', 'frame')
    return [hd, leg]


def a_shin():
    kd = drum('knee_drum', 0.22, 0.42, 'frame', [0, 0, 0])
    kg = [(-0.15, 0.3), (-0.33, 0.13), (-0.36, -0.25), (-0.23, -0.44), (-0.12, -0.28)]
    knee = loft('knee_guard', 'x', [(-0.26, kg), (0.26, kg)], lambda k, j: 'cyan', 'cyan', 'cyan')
    leg = L('shin', 'y', [
        (-0.22, sec_a(0.23, 0.26, 0.08, oz=0.03)),
        (-0.82, sec_a(0.3, 0.36, 0.12, oz=0.07)),
        (-1.5, sec_a(0.28, 0.33, 0.11, oz=0.04)),
        (-1.79, sec_a(0.26, 0.3, 0.1)),
    ], {0: {'*': 'white', 'f': 'cyan', 'fr': 'cyan', 'fl': 'cyan'},
        1: {'*': 'white', 'b': 'silver'},
        2: {'*': 'silver'}},
        'frame', 'frame')
    return [kd, knee, leg]


def a_foot():
    """Long, narrow and pointed."""
    return boot(A.ankle, 0.27, 0.56, 'white', 'cyan')


A_PARTS = {
    'pelvis': a_pelvis, 'torso': a_torso, 'head': a_head, 'pauldron': a_pauldron,
    'upper_arm': a_upper_arm, 'forearm': a_forearm, 'hand': a_hand,
    'thigh': a_thigh, 'shin': a_shin, 'foot': a_foot,
}


# ---- twin B, "the 0": short and stocky, pink -------------------------------------------------

B = Dims(ankle=0.5525, shin=1.25, thigh=1.25, hip_x=0.85, waist=0.38, shoulder=(1.5, 1.88, 0.05),
         neck=(0.0, 2.28, -0.06), upper=1.05, fore=1.15, hand=0.8)
B.grip = round(-0.42*B.hand, 4)


def b_pelvis():
    core = L('core', 'y', [
        (0.32, sec_b(0.72, 0.64)),
        (0.02, sec_b(0.84, 0.72)),
        (-0.48, sec_b(0.36, 0.38, oz=-0.03)),
    ], {0: {'*': 'white', 'f': 'pink', 'b': 'silver'},
        1: {'*': 'frame', 'f': 'white'}},
        'silver', 'frame')
    axle = drum('hip_axle', 0.24, 2*B.hip_x, 'frame', [0, 0, 0], caps=False)
    return [core, axle]


def b_cell(at=(0.0, 1.4, 1.22)):
    """The round fusion cell: a clear drum (its axle along X) round a pink glow, on a mount;
    seen side-on, a disc: the 0."""
    x, y, z = at
    return [box('cell_mount', [0.44, 0.74, 0.5], 'frame', [x, y, z-0.38]),
            cyl_x('cell', 0.58, 0.76, 8, 'pshell', [x, y, z]),
            drum('cell_core', 0.36, 0.56, 'pglow', [x, y, z])]


def b_torso():
    """The barrel chest: deep seen side-on, a pink belly band, a glowing ring on the chest (the
    0); the round fusion cell on the back."""
    abdomen = L('abdomen', 'y', [
        (-0.12, sec_b(0.44, 0.4)),
        (0.5, sec_b(0.52, 0.46)),
    ], 'frame', None, None)
    chest = L('chest', 'y', [
        (0.38, sec_b(0.76, 0.64)),
        (0.9, sec_b(1.2, 0.9, oz=-0.02)),
        (1.85, sec_b(1.28, 0.94, oz=-0.03)),
        (2.4, sec_b(0.66, 0.54)),
    ], {0: {'*': 'pink'},
        1: {'*': 'white', 'fr': 'pink', 'fl': 'pink'},
        2: {'*': 'silver'}},
        'frame', 'frame')
    ring = cyl_z('zero', 0.3, 0.12, 6, 'frame', [0, 1.3, -0.95], faces={'bottom': 'pglow'})
    hole = box('zero_hole', [0.2, 0.2, 0.1], 'dark', [0, 1.3, -1.02])
    collar = L('collar', 'y', [
        (2.3, sec_b(0.46, 0.4)),
        (2.5, sec_b(0.34, 0.32)),
    ], 'white', None, 'frame')
    return [abdomen, chest, ring, hole, collar] + b_cell()


def b_head():
    """A round helmet, wider than tall, a pink glow under a clear visor, big round ear discs
    (seen side-on, the 0)."""
    neck = cyl_y('neck', 0.24, 0.4, 6, 'frame', [0, 0.12, 0], caps=False)
    helmet = L('helmet', 'y', [
        (0.16, sec_b(0.34, 0.34)),
        (0.36, sec_b(0.48, 0.47)),
        (0.74, sec_b(0.5, 0.49)),
        (1.18, sec_b(0.28, 0.28)),
    ], {0: {'*': 'white', 'f': 'silver'},
        1: {'*': 'white', 'f': 'pglow', 'fr': 'pglow', 'fl': 'pglow'},
        2: {'*': 'white', 'b': 'pink', 'br': 'pink', 'bl': 'pink'}},
        'frame', 'pink')
    visor = H.chevron('visor', 'pshell',
                      [(-0.46, 0.36), (-0.58, 0.42), (-0.56, 0.7), (-0.47, 0.76)],
                      [(-0.4, 0.38), (-0.47, 0.42), (-0.46, 0.68), (-0.4, 0.72)], 0.24)
    ears = cyl_x('ears', 0.34, 1.06, 8, 'silver', [0, 0.62, 0.04],
                 faces={'top': 'pink', 'bottom': 'pink'})
    return [neck, helmet, visor, ears]


def b_pauldron():
    """A big round dome; the outer face (flat) carries the mark on a pink field."""
    dome = L('dome', 'y', [
        (0.62, sec_a(0.3, 0.34, 0.16, ox=0.2)),
        (0.3, sec_a(0.56, 0.6, 0.26, ox=0.3)),
        (-0.3, sec_a(0.56, 0.6, 0.26, ox=0.3)),
        (-0.52, sec_a(0.42, 0.46, 0.2, ox=0.3)),
    ], {0: {'*': 'white'}, 1: {'*': 'pink', 'r': 'emblem_p'}, 2: {'*': 'silver'}},
        'frame', 'white')
    return [dome]


def b_upper_arm():
    sh = drum('shoulder_drum', 0.33, 0.5, 'frame', [0, 0, 0], caps=False)
    arm = L('arm', 'y', [
        (-0.2, sec_b(0.24, 0.26)),
        (-0.95, sec_b(0.22, 0.24)),
    ], 'frame', None, 'frame')
    return [sh, arm]


def b_gauntlet():
    return L('gauntlet', 'y', [
        (-0.18, sec_b(0.32, 0.34)),
        (-0.62, sec_b(0.44, 0.44, oz=0.02)),
        (-1.12, sec_b(0.33, 0.34)),
    ], {0: {'*': 'white'}, 1: {'*': 'pink', 'b': 'white', 'br': 'white', 'bl': 'white'}},
        'white', 'frame')


def b_forearm():
    el = drum('elbow_drum', 0.27, 0.46, 'silver', [0, 0, 0])
    g = [(0.16, 0.28), (0.4, 0.1), (0.42, -0.3), (0.24, -0.46)]
    guard = loft('elbow_guard', 'x', [(-0.27, g), (0.27, g)], lambda k, j: 'white',
                 'white', 'white')
    return [el, b_gauntlet(), guard]


def b_hand():
    return fist(B.hand, 'pink')


def b_thigh():
    """Short and thick; the hip drum's outer end a pink disc (seen side-on, round hips)."""
    hd = cyl_x('hip_drum', 0.4, 0.5, 8, 'silver', [0, 0, 0],
               faces={'top': 'pink', 'bottom': 'pink'})
    leg = L('thigh', 'y', [
        (-0.22, sec_b(0.34, 0.38)),
        (-0.6, sec_b(0.42, 0.48, oz=-0.02)),
        (-1.16, sec_b(0.32, 0.36)),
    ], {0: {'*': 'white', 'f': 'pink'}, 1: {'*': 'white', 'b': 'frame'}},
        'frame', 'frame')
    return [hd, leg]


def b_shin():
    kd = drum('knee_drum', 0.28, 0.54, 'frame', [0, 0, 0])
    kg = [(-0.2, 0.36), (-0.44, 0.18), (-0.47, -0.26), (-0.3, -0.5), (-0.14, -0.32)]
    knee = loft('knee_guard', 'x', [(-0.34, kg), (0.34, kg)], lambda k, j: 'pink', 'pink', 'pink')
    leg = L('shin', 'y', [
        (-0.24, sec_b(0.34, 0.37, oz=0.04)),
        (-0.72, sec_b(0.46, 0.52, oz=0.08)),
        (-1.18, sec_b(0.42, 0.46, oz=0.04)),
        (-1.42, sec_b(0.38, 0.42)),
    ], {0: {'*': 'white', 'f': 'pink'},
        1: {'*': 'white', 'b': 'silver'},
        2: {'*': 'silver'}},
        'frame', 'frame')
    return [kd, knee, leg]


def b_foot():
    """Wide, short and blunt: a big round-toed boot."""
    return boot(B.ankle, 0.46, 0.62, 'pink', 'white')


B_PARTS = {
    'pelvis': b_pelvis, 'torso': b_torso, 'head': b_head, 'pauldron': b_pauldron,
    'upper_arm': b_upper_arm, 'forearm': b_forearm, 'hand': b_hand,
    'thigh': b_thigh, 'shin': b_shin, 'foot': b_foot,
}


# ---- the combined form: twin A above, twin B below -------------------------------------------
# Each twin part is drawn scaled from the twin's own (a group's scale), so the shapes, colours
# and joints carry over; the joints scale with them. Built FINE: rounder sections, smoother
# drums, the fists' plates.

S_TORSO = [1.9, 1.65, 1.65]     # twin A's torso, opened out into a broad chest
S_HEAD = [1.5, 1.5, 1.5]
S_ARM = [1.7, 1.6, 1.7]         # twin A's arms: 1.6 long, a little thicker
S_HIPS = [1.5, 1.5, 1.5]        # twin B's pelvis
S_LEG = [1.5, 1.76, 1.5]        # twin B's thighs and shins: longer
S_FOOT = [1.55, 1.55, 1.55]

C = Dims(ankle=B.ankle*S_FOOT[1], shin=B.shin*S_LEG[1], thigh=B.thigh*S_LEG[1],
         hip_x=B.hip_x*S_HIPS[0], waist=1.05,
         shoulder=tuple(A.shoulder[k]*S_TORSO[k] for k in range(3)),
         neck=tuple(A.neck[k]*S_TORSO[k] for k in range(3)),
         upper=A.upper*S_ARM[1], fore=A.fore*S_ARM[1], hand=A.hand*S_ARM[1])
C.grip = round(A.grip*S_ARM[1], 4)


def combined(fn):
    """A combined part's builder: built FINE."""
    def build():
        with fine():
            return fn()
    build.__name__ = fn.__name__
    build.__doc__ = fn.__doc__
    return build


@combined
def c_pelvis():
    """Twin B's hips, 1.5 times; its forearms folded down as the hip skirts and its round
    cell behind; on top the waist coupling (combined only): a chrome collar, a hazard band
    (a pinch point) and the fusion glow."""
    hips = group('twin_b_hips', b_pelvis(), scale=S_HIPS)
    skirts = mirror('hip_skirts', [group('skirt', [b_gauntlet()], translate=[2.0, 0.52, 0.06],
                                         rotate=[0, 0, 6], scale=[1.0, 1.0, 1.25])])
    cell = group('twin_b_cell', b_cell((0.0, 0.0, 0.0)), translate=[0, -0.05, 1.5],
                 scale=[1.25, 1.25, 1.25])
    coupling = [cyl_y('coupling', 0.62, 0.8, 8, 'silver', [0, 0.82, 0]),
                cyl_y('coupling_band', 0.68, 0.14, 8, 'hazard', [0, 0.6, 0], caps=False),
                cyl_y('fusion_ring', 0.7, 0.14, 8, 'fglow', [0, 0.84, 0], caps=False)]
    return [hips, skirts, cell] + coupling


def folded_leg():
    """Twin A's leg folded up the back (in twin A's units): the thigh's white and cyan, the foot
    at the bottom as a thruster."""
    leg = L('folded_leg', 'y', [
        (0.5, sec_a(0.14, 0.18, 0.05)),
        (0.95, sec_a(0.17, 0.24, 0.07, oz=0.02)),
        (2.3, sec_a(0.12, 0.16, 0.04, oz=0.03)),
    ], {0: {'*': 'white', 'b': 'cyan', 'br': 'cyan', 'bl': 'cyan'}, 1: {'*': 'white', 'b': 'cyan'}},
        'frame', 'silver')
    nozzle = cyl_y('thruster', 0.13, 0.22, 6, 'frame', [0, 0.45, 0.0], faces={'bottom': 'glow'})
    return [leg, nozzle]


@combined
def c_torso():
    """Twin A's torso opened out (1.9 wide, 1.65 tall and deep), its legs folded up the back."""
    chest = group('twin_a_torso', a_torso(combined=True) + [
        box('fold_mount', [0.86, 0.9, 0.26], 'frame', [0, 1.45, 0.52]),
        mirror('back_fins', [group('fin', folded_leg(), translate=[0.3, 0.0, 0.72],
                                   rotate=[-6, 0, -4])])], scale=S_TORSO)
    return [chest]


@combined
def c_head():
    return [group('twin_a_head', a_head(combined=True), scale=S_HEAD)]


@combined
def c_pauldron():
    """The big shoulder plates (combined only): cyan in front, pink behind, the mark on the outer
    face, a clear fin rising from the top."""
    pl = L('plate', 'y', [
        (0.86, crect(0.5, 0.6, 0.18, 0.16, ox=0.2)),
        (0.4, crect(0.84, 0.98, 0.3, 0.26, ox=0.38)),
        (-0.42, crect(0.84, 0.98, 0.3, 0.26, ox=0.38)),
        (-0.64, crect(0.72, 0.86, 0.24, 0.2, ox=0.4)),
    ], {0: {'*': 'white', 'f': 'cyan', 'fr': 'cyan', 'fl': 'cyan',
            'b': 'pink', 'br': 'pink', 'bl': 'pink'},
        1: {'*': 'white', 'r': 'emblem', 'f': 'cyan', 'b': 'pink'},
        2: {'*': 'silver'}},
        'frame', 'white')
    fin = {'id': 'fin', 'op': 'extrude', 'depth': 0.08, 'material': 'shell',
           'points': [[-0.5, 0.0], [0.62, 0.0], [0.86, 0.36], [-0.1, 0.42]],
           'transform': {'rotate': [0, 90, 0], 'translate': [0.66, 0.82, 0.05]}}
    return [pl, fin]


@combined
def c_upper_arm():
    return [group('twin_a_upper_arm', a_upper_arm(), scale=S_ARM)]


@combined
def c_forearm():
    return [group('twin_a_forearm', a_forearm(), scale=S_ARM)]


@combined
def c_hand():
    return [group('twin_a_hand', a_hand(), scale=S_ARM)]


@combined
def c_thigh():
    tag = box('serial_plate', [0.08, 0.5, 0.9], 'white', [0.62, -1.3, 0.0],
              faces={'right': 'serial'})
    return [group('twin_b_thigh', b_thigh(), scale=S_LEG), tag]


@combined
def c_shin():
    return [group('twin_b_shin', b_shin(), scale=S_LEG)]


@combined
def c_foot():
    return [group('twin_b_foot', b_foot(), scale=S_FOOT)]


C_PARTS = {
    'pelvis': c_pelvis, 'torso': c_torso, 'head': c_head, 'pauldron': c_pauldron,
    'upper_arm': c_upper_arm, 'forearm': c_forearm, 'hand': c_hand,
    'thigh': c_thigh, 'shin': c_shin, 'foot': c_foot,
}
SIDED = H.SIDED - {'sword'}



# ---- the rigs' notes for the animators ------------------------------------------------------

RANGES_A = {
    'pelvis':    ('twin A\'s hips; the hip axle', 'x -25..25, y -40..40, z -10..10'),
    'torso':     ('the slim chest, the cyan core and the fusion cell on the back', 'x -40..35, y -60..60, z -20..20'),
    'head':      ('the tall head and its blade fin (the 1)', 'x -30..30, y -60..60, z -15..15'),
    'pauldron':  ('the small shoulder plate; follows the upper arm part way', 'about 0.35 of the upper arm\'s x and 0.5 of its z'),
    'upper_arm': ('the shoulder drum and the thin upper arm', 'x -70..190, y -45..45, z: out -110..in 25 (sign by side)'),
    'forearm':   ('the gauntlet', 'x 0..150 (forward only: the elbow), y -30..30'),
    'hand':      ('the fist (an empty weapon mount at its middle)', 'x -70..70, y -40..40, z -35..35'),
    'thigh':     ('the long thigh', 'x -60..110, z -40..30'),
    'shin':      ('the long shin', 'x -150..0 (back only: the knee)'),
    'foot':      ('the pointed foot', 'x -45..45, z -15..15'),
}
RANGES_B = {
    'pelvis':    ('twin B\'s round hips; the hip axle', 'x -20..20, y -35..35, z -8..8'),
    'torso':     ('the barrel chest, the pink ring and the round cell on the back', 'x -35..30, y -55..55, z -15..15'),
    'head':      ('the round head (it turns less: the collar is high)', 'x -20..25, y -45..45, z -10..10'),
    'pauldron':  ('the big shoulder dome; follows the upper arm part way', 'about 0.35 of the upper arm\'s x and 0.5 of its z'),
    'upper_arm': ('the shoulder drum and the short upper arm', 'x -60..180, y -40..40, z: out -100..in 20 (sign by side)'),
    'forearm':   ('the big round gauntlet', 'x 0..140 (forward only: the elbow), y -30..30'),
    'hand':      ('the big fist (an empty weapon mount at its middle)', 'x -70..70, y -40..40, z -35..35'),
    'thigh':     ('the short thick thigh, a round pink hip disc', 'x -45..100, z -35..30'),
    'shin':      ('the short shin, the pink knee', 'x -140..0 (back only: the knee)'),
    'foot':      ('the big round-toed foot', 'x -40..40, z -15..15'),
}
RANGES_C = {
    'pelvis':    ('twin B\'s hips (1.5x), its folded forearms as the skirts, its cell behind, the waist coupling on top', 'x -15..15, y -35..35, z -8..8'),
    'torso':     ('twin A\'s torso (1.9 x 1.65 x 1.65), its legs folded up the back as fins', 'x -40..30, y -60..60, z -15..15'),
    'head':      ('twin A\'s head (1.5x) with the V crest', 'x -25..30, y -50..50, z -12..12'),
    'pauldron':  ('the big shoulder plate (combined only); follows the upper arm part way', 'about 0.35 of the upper arm\'s x and 0.5 of its z'),
    'upper_arm': ('twin A\'s upper arm (1.6x)', 'x -65..190, y -40..40, z: out -100..in 25 (sign by side)'),
    'forearm':   ('twin A\'s gauntlet (1.6x)', 'x 0..145 (forward only: the elbow), y -30..30'),
    'hand':      ('twin A\'s fist (1.6x; an empty weapon mount at its middle)', 'x -70..70, y -40..40, z -35..35'),
    'thigh':     ('twin B\'s thigh (1.5 x 1.76 x 1.5)', 'x -50..105, z -35..30 (the hip skirts hang outside: z out past -25 crosses them)'),
    'shin':      ('twin B\'s shin (1.5 x 1.76 x 1.5)', 'x -140..0 (back only: the knee)'),
    'foot':      ('twin B\'s foot (1.55x)', 'x -40..40, z -15..15'),
}


# ---- the skeleton, posing, assembling --------------------------------------------------------

def skeleton(d):
    """(id, parent, offset, rest rotation, part, side), parents first: the Hero's ids and order
    (make_hero.skeleton) with this body's offsets."""
    out = [('pelvis', None, [0, d.hip_y, 0], None, 'pelvis', None),
           ('torso', 'pelvis', [0, d.waist, 0], None, 'torso', None),
           ('head', 'torso', list(d.neck), None, 'head', None)]
    for s in 'rl':
        x = d.shoulder[0] if s == 'l' else -d.shoulder[0]
        at = [x, d.shoulder[1], d.shoulder[2]]
        out += [(f'pauldron_{s}', 'torso', at, None, 'pauldron', s),
                (f'upper_arm_{s}', 'torso', at, None, 'upper_arm', s),
                (f'forearm_{s}', f'upper_arm_{s}', [0, -d.upper, 0], None, 'forearm', s),
                (f'hand_{s}', f'forearm_{s}', [0, -d.fore, 0], None, 'hand', s)]
    for s in 'rl':
        x = d.hip_x if s == 'l' else -d.hip_x
        out += [(f'thigh_{s}', 'pelvis', [x, 0, 0], None, 'thigh', s),
                (f'shin_{s}', f'thigh_{s}', [0, -d.thigh, 0], None, 'shin', s),
                (f'foot_{s}', f'shin_{s}', [0, -d.shin, 0], None, 'foot', s)]
    return out


def world_frames(d, stance, drop=0.0):
    """{joint id: (rotation, position)} in the asset's frame."""
    out = {}
    for jid, parent, offset, rest, _, _ in skeleton(d):
        r = H.rot(stance.get(jid, [0, 0, 0]))
        if parent is None:
            out[jid] = (r, [offset[0], offset[1]-drop, offset[2]])
        else:
            pr, pt = out[parent]
            out[jid] = (H.mm(pr, r), H.add(pt, H.mv(pr, offset)))
    return out


def solve_leg(d, side, stance, drop):
    """Knee and ankle angles that put this ankle d.ankle above the ground with the sole level
    (make_hero.solve_leg with this body's joints)."""
    def ankle_y(k):
        st = dict(stance)
        st[f'shin_{side}'] = [k, 0, 0]
        return world_frames(d, st, drop)[f'foot_{side}'][1][1]
    lo, hi = -150.0, 0.0
    for _ in range(60):
        mid = (lo+hi)/2
        if ankle_y(mid) > d.ankle+0.01:
            lo = mid
        else:
            hi = mid
    k = round((lo+hi)/2, 2)
    px, th = stance.get('pelvis', [0, 0, 0])[0], stance[f'thigh_{side}']
    return [k, 0, 0], [round(-(px+th[0]+k), 2), 0, round(-th[2], 2)]


def pose(d, base, drop):
    st = dict(base)
    for s in 'rl':
        ua = st.get(f'upper_arm_{s}', [0, 0, 0])
        st[f'pauldron_{s}'] = [round(ua[0]*0.35, 2), 0, round(ua[2]*0.5, 2)]
    for s in 'rl':
        if f'thigh_{s}' in st and f'shin_{s}' not in st:
            st[f'shin_{s}'], st[f'foot_{s}'] = solve_leg(d, s, st, drop)
    return st


def assemble(body, stance, drop=0.0):
    """The rig as nested groups, posed."""
    sk = skeleton(body['dims'])
    kids = {}
    for jid, parent, *_ in sk:
        kids.setdefault(parent, []).append(jid)

    def node(jid):
        _, parent, offset, _, part, side = next(e for e in sk if e[0] == jid)
        t = list(offset)
        if parent is None:
            t[1] -= drop
        return {'id': jid, 'op': 'group',
                'children': geometry(body, part, side) + [node(k) for k in kids.get(jid, [])],
                'transform': T([round(c, 4) for c in t], stance.get(jid))}
    return [node('pelvis')]


def geometry(body, part, side):
    return H.geometry(part, side, body['parts'])


def used_materials(nodes):
    return {k: v for k, v in MATERIALS.items() if k in H.used(nodes)}


def recipe(name, nodes, budget, vertices=2048):
    r = H.recipe(name, nodes, budget, vertices, materials=MATERIALS)
    r['materials'] = used_materials(nodes)
    return r


# ---- the guard stances ------------------------------------------------------------------------
# The right side (-X) leads, as the Hero's: right foot forward, both fists up.

# Twin A: upright and light, a fencer's guard: the lead fist high and out, the rear one by the
# chin.
A_DROP = 0.3
A_STANCE = pose(A, {
    'pelvis': [0, -10, 0], 'torso': [-4, -16, 0], 'head': [-2, 14, 0],
    'thigh_r': [26, 0, -4], 'thigh_l': [-18, 0, 4],
    'upper_arm_r': [34, 0, -12], 'forearm_r': [76, 0, 6], 'hand_r': [-10, 0, 0],
    'upper_arm_l': [20, 0, 16], 'forearm_l': [100, 0, -10], 'hand_l': [-8, 0, 0],
}, A_DROP)

# Twin B: low and wide, a brawler's: hunched over its barrel chest, both big fists forward.
B_DROP = 0.32
B_STANCE = pose(B, {
    'pelvis': [0, -6, 0], 'torso': [8, -10, 0], 'head': [-8, 8, 0],
    'thigh_r': [24, 0, -10], 'thigh_l': [-16, 0, 10],
    'upper_arm_r': [26, 0, -22], 'forearm_r': [70, 0, 2], 'hand_r': [-14, 0, 0],
    'upper_arm_l': [30, 0, 22], 'forearm_l': [78, 0, -2], 'hand_l': [-14, 0, 0],
}, B_DROP)

# The combined form: the Hero's heroic guard, planted wide, fists up.
C_DROP = 0.55
C_STANCE = pose(C, {
    'pelvis': [0, -8, 0], 'torso': [-6, -14, 0], 'head': [-4, 12, 0],
    'thigh_r': [30, 0, -7], 'thigh_l': [-20, 0, 7],
    'upper_arm_r': [28, 0, -16], 'forearm_r': [72, 0, 4], 'hand_r': [-16, 0, 0],
    'upper_arm_l': [34, 0, 18], 'forearm_l': [88, 0, -6], 'hand_l': [-12, 0, 0],
}, C_DROP)

# ---- the docked pose: where combine ends and split starts (MOVES.md, "Switching forms") -----
# All three on one root. Twin B stands under twin A, knees bent, leaning into it, arms in along
# its thighs, head tucked down into its chest: it becomes the legs. Twin A sits on twin B's
# shoulders, its pelvis lifted (a negative drop: the pose's offset up) to about the combined
# torso joint, its legs folded up behind it, arms out. The combined form crouches deep in the
# same place, its pelvis about at twin B's, its torso joint at twin A's pelvis. The flash hides
# the swap (the combined form is about 1.5 times the twins' size), so the joints need only be
# near each other; combined_map in twins.rig.json gives each one's place.

B_DOCK_DROP = 0.5
B_DOCKED = pose(B, {
    'pelvis': [0, 0, 0], 'torso': [-14, 0, 0], 'head': [-30, 0, 0],
    'thigh_r': [30, 0, -6], 'thigh_l': [30, 0, 6],
    'upper_arm_r': [22, 0, -8], 'forearm_r': [36, 0, 0], 'hand_r': [0, 0, 0],
    'upper_arm_l': [22, 0, 8], 'forearm_l': [36, 0, 0], 'hand_l': [0, 0, 0],
}, B_DOCK_DROP)

A_DOCK_DROP = -1.55
A_DOCKED = pose(A, {
    'pelvis': [0, 0, 0], 'torso': [-4, 0, 0], 'head': [6, 0, 0],
    'thigh_r': [-100, 0, -8], 'shin_r': [-130, 0, 0], 'foot_r': [40, 0, 0],
    'thigh_l': [-100, 0, 8], 'shin_l': [-130, 0, 0], 'foot_l': [40, 0, 0],
    'upper_arm_r': [20, 0, -38], 'forearm_r': [60, 0, 0], 'hand_r': [0, 0, 0],
    'upper_arm_l': [20, 0, 38], 'forearm_l': [60, 0, 0], 'hand_l': [0, 0, 0],
}, A_DOCK_DROP)

C_DOCK_DROP = 1.4
C_DOCKED = pose(C, {
    'pelvis': [0, 0, 0], 'torso': [-10, 0, 0], 'head': [4, 0, 0],
    'thigh_r': [52, 0, -8], 'thigh_l': [52, 0, 8],
    'upper_arm_r': [20, 0, -30], 'forearm_r': [70, 0, 0], 'hand_r': [0, 0, 0],
    'upper_arm_l': [20, 0, 30], 'forearm_l': [70, 0, 0], 'hand_l': [0, 0, 0],
}, C_DOCK_DROP)
DOCKED = {'twin_a': (A_DOCKED, A_DOCK_DROP), 'twin_b': (B_DOCKED, B_DOCK_DROP),
          'twins': (C_DOCKED, C_DOCK_DROP)}
DOCK_NOTE = {
    'twin_a': "docked (combine's last twin frame, 0-based 22; split's first, 12): on twin B's "
              "shoulders, the pelvis lifted 1.55 m (drop -1.55: offset [0, 1.55]) to about the "
              "combined torso joint, legs folded up behind, arms out",
    'twin_b': "docked (combine's last twin frame, 0-based 22; split's first, 12): under twin A, "
              "knees bent, leaning in, arms along the thighs, head tucked: it becomes the legs",
    'twins': "docked (combine's frames before the swap, to 0-based 23; split's from 12): the "
             "deep crouch the twins' docked poses stand in for; its pelvis about at twin B's, "
             "its torso joint at twin A's pelvis",
}


def flex_pose(d, drop):
    """Every joint near the end of its range (make_hero's FLEX_BASE), the knees solved free."""
    return pose(d, {
        'pelvis': [10, 0, 0], 'torso': [22, 28, -6], 'head': [-26, -24, 0],
        'upper_arm_r': [165, 0, -12], 'forearm_r': [70, 0, 0], 'hand_r': [-55, 0, 0],
        'upper_arm_l': [-45, 0, 34], 'forearm_l': [135, 0, 0], 'hand_l': [55, 0, 20],
        'thigh_r': [95, 0, -4], 'shin_r': [-125, 0, 0], 'foot_r': [-38, 0, 0],
        'thigh_l': [-28, 0, 6], 'shin_l': [-70, 0, 0], 'foot_l': [42, 0, 0],
    }, drop)


# ---- cameras ---------------------------------------------------------------------------------

def cameras(body, stance, drop):
    """Side views at game distance (31.2 m: the 12 m frame at about 80 px, a twin at about
    50 px), nearer ones, quarters, the head close up and each fist."""
    d = body['dims']
    h = d.hip_y+d.waist+d.neck[1]+1.0
    mid, mz = h*0.48, -1.0*h/12
    near = 17.0*h/12
    cams = [
        {'name': 'side_facing_right', 'eye': [-31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_facing_left', 'eye': [31.2, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_right_near', 'eye': [-near, mid, mz], 'target': [0, mid, mz]},
        {'name': 'side_left_near', 'eye': [near, mid, mz], 'target': [0, mid, mz]},
        {'name': 'front_quarter', 'eye': [-near*0.7, h*0.75, -near*0.95], 'target': [0, mid, mz]},
        {'name': 'back_quarter', 'eye': [near*0.7, h*0.75, near*0.85], 'target': [0, mid, 0]},
        {'name': 'front', 'eye': [0, mid, -near*1.1], 'target': [0, mid, 0]},
    ]
    fr = world_frames(d, stance, drop)
    hr, hp = fr['head']
    hc = H.add(hp, H.mv(hr, [0, 0.55*h/12*2, -0.1]))
    hd = 4.2*h/12
    for name, dv in (('head_front', [0, 0.15, -1]), ('head_side_right', [-1, 0.1, 0]),
                     ('head_side_left', [1, 0.1, 0]), ('head_three_quarter', [-0.7, 0.3, -0.75])):
        v = H.mv(hr, dv)
        ln = math.sqrt(H.dot(v, v))
        cams.append({'name': name, 'eye': [round(hc[k]+v[k]*hd/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in hc]})
    for sd, sx in (('r', -1), ('l', 1)):
        r, p = fr[f'hand_{sd}']
        c = H.add(p, H.mv(r, [0, d.grip, 0]))
        dv = [sx, 0.2, -0.6]
        ln = math.sqrt(H.dot(dv, dv))
        cams.append({'name': f'fist_{sd}', 'eye': [round(c[k]+dv[k]*hd/ln, 3) for k in range(3)],
                     'target': [round(v, 3) for v in c]})
    return cams


def flex_cameras(body, stance, drop):
    d = body['dims']
    h = d.hip_y+d.waist+d.neck[1]+1.0
    s = h/12
    cams = [
        {'name': 'flex_side_right', 'eye': [-17.0*s, 5.0*s, -1.0*s], 'target': [0, 5.0*s, -1.0*s]},
        {'name': 'flex_side_left', 'eye': [17.0*s, 5.0*s, -1.0*s], 'target': [0, 5.0*s, -1.0*s]},
        {'name': 'flex_front_quarter', 'eye': [-11.0*s, 7.0*s, -13.0*s], 'target': [0, 5.0*s, -1.0*s]},
    ]
    fr = world_frames(d, stance, drop)
    for jid, dv, dist in (('foot_r', [-1, 0.3, -0.2], 4.2), ('foot_l', [1, 0.3, 0.1], 4.2),
                          ('shin_r', [-1, 0.2, 0.3], 4.5), ('shin_l', [1, 0.2, -0.2], 4.5),
                          ('forearm_l', [1, 0.3, -0.3], 4.0), ('hand_r', [-1, 0.2, -0.4], 3.6),
                          ('torso', [-1, 0.2, -0.6], 6.0), ('upper_arm_r', [-1, 0.0, -0.3], 4.5)):
        _, p = fr[jid]
        ln = math.sqrt(H.dot(dv, dv))
        cams.append({'name': f'flex_{jid}',
                     'eye': [round(p[k]+dv[k]*dist*s/ln, 3) for k in range(3)],
                     'target': [round(c, 3) for c in p]})
    return cams


# ---- writing ---------------------------------------------------------------------------------

def body_rig(body, stance, drop, part_recipes):
    d = body['dims']
    name = body['name']
    parts = []
    for jid, parent, offset, rest, part, side in skeleton(d):
        pname = H.part_name(name, part, side)
        e = {'id': jid, 'parent': parent, 'offset': [round(c, 4) for c in offset]}
        e['recipe'] = f'parts/{pname}.asset.json'
        e['asset'] = f'ASSET_{pname.upper()}'
        e.update(H.part_facts(part_recipes[pname]))
        role, rng = body['ranges'][part]
        e['role'] = role
        e['range'] = rng
        parts.append(e)
    mounts = [{'id': f'weapon_{s}', 'parent': f'hand_{s}', 'offset': [0, d.grip, 0],
               'rotate': H.MOUNT_ROTATE, 'part': None,
               'note': "empty: the middle of the fist (the twins fight with their fists)"}
              for s in 'rl']
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
        'body': body['note'],
        'height': body['height'],
        'parts': parts,
        'mounts': mounts,
        'poses': {'guard': {'drop': round(drop, 4), 'rotate': dict(stance),
                            'note': body['guard_note']},
                  'docked': {'drop': DOCKED[name][1], 'rotate': dict(DOCKED[name][0]),
                             'note': DOCK_NOTE[name]}},
        'triangles': sum(p['triangles'] for p in parts),
    }
    if body.get('extra'):
        rig.update(body['extra'])
    return rig


def write_body(body, stance, drop, budget):
    folder, name = body['folder'], body['name']
    H.write(folder/f'{name}.asset.json', recipe(name, assemble(body, stance, drop), budget))
    H.write(folder/f'{name}_rest.asset.json', recipe(f'{name}_rest', assemble(body, {}), budget))
    written = {}
    for part in body['parts']:
        for side in (('l', 'r') if part in SIDED else (None,)):
            pname = H.part_name(name, part, side)
            nodes = geometry(body, part, side)
            r = recipe(pname, nodes, 400, 512)
            H.write(folder/'parts'/f'{pname}.asset.json', r)
            written[pname] = r
    for p in (folder/'parts').glob(f'{name}_*.asset.json'):
        if p.name[:-len('.asset.json')] not in written:
            p.unlink()
    flex_drop = 0.285*body['dims'].hip_y
    flex = flex_pose(body['dims'], flex_drop)
    H.write(folder/f'{name}_flex.asset.json',
            recipe(f'{name}_flex', assemble(body, flex, flex_drop), budget))
    H.write(folder/'cameras.json', cameras(body, stance, drop))
    H.write(folder/'cameras_flex.json', flex_cameras(body, flex, flex_drop))
    H.write(folder/'asset-preview.json', LOOK)
    return written


def height(body):
    """The rest pose's top (from the assembled recipe's bounds)."""
    return H.part_facts(recipe('h', assemble(body, {}), 4000))['bounds']['max'][1]


def fight_xy(p):
    return [round(-p[2], 3), round(p[1], 3)]


def combined_map():
    """Where each twin's parts sit in the combined form, for `combine` and `split`: per combined
    joint, the twin and part it is made of and its scale; every joint's place in the docked pose
    of each body and in the guards (fight-local x forward, y up, metres from the root)."""
    src = {'pelvis': ('twin_b', 'pelvis (1.5x); its forearms are the hip skirts, its round cell '
                      'rides behind, its torso and head fold away inside', S_HIPS),
           'torso': ('twin_a', 'torso (1.9 x 1.65 x 1.65); its legs fold up the back as the fins',
                     S_TORSO),
           'head': ('twin_a', 'head', S_HEAD),
           'pauldron': (None, 'combined only', None),
           'upper_arm': ('twin_a', 'upper_arm', S_ARM), 'forearm': ('twin_a', 'forearm', S_ARM),
           'hand': ('twin_a', 'hand', S_ARM),
           'thigh': ('twin_b', 'thigh', S_LEG), 'shin': ('twin_b', 'shin', S_LEG),
           'foot': ('twin_b', 'foot', S_FOOT)}
    joints = {}
    for jid, parent, offset, _, part, side in skeleton(C):
        who, what, sc = src[part]
        joints[jid] = {'from': who,
                       'part': what if part in ('pelvis', 'torso') or who is None
                       else f'{part}_{side}' if side else part,
                       'scale': sc}
    places = {}
    for key, d in (('twins', C), ('twin_a', A), ('twin_b', B)):
        dock = world_frames(d, *DOCKED[key])
        guard = world_frames(d, *STANCES[key])
        places[key] = {'docked': {j: fight_xy(dock[j][1]) for j, *_ in skeleton(d)},
                       'guard': {j: fight_xy(guard[j][1]) for j, *_ in skeleton(d)}}
    return {
        'note': "The combined form is twin A (head, torso, arms) on twin B (hips, legs), drawn "
                "about 1.5 to 1.9 times their split size. The bodies swap on the flash "
                "(combine's 0-based frame 23, split's 12), so the twins' combine ends, and their "
                "split starts, in their rigs' 'docked' pose, and the combined form's combine "
                "holds, and its split reaches, its own 'docked' pose before the swap. The three "
                "docked poses are made to line up on one root: twin B's pelvis near the combined "
                "pelvis, twin A's pelvis (lifted 1.55 m: its docked pose's drop is -1.55) near "
                "the combined torso joint, twin A's shoulders and head under the combined ones. "
                "'joints': what each combined part is made of; 'places': every joint of each body "
                "in its docked pose and its guard. models/twins/twins_docking.asset.json draws "
                "the twins docked, twins_docked.asset.json the combined form docked, for "
                "review with the same cameras (cameras_docking.json).",
        'joints': joints,
        'places': places,
    }


def docking_recipe():
    """For review: the two twins docked on one root (twins_docking, at z = -6) and the combined
    form docked (twins_docked, at z = +6): the same cameras see them side by side."""
    def at(key, z):
        body = BODIES[key]
        st, drop = DOCKED[key]
        return group(f'{key}_docked', assemble(body, st, drop), translate=[0, 0, z])
    split = recipe('twins_docking', [at('twin_b', -6.0), at('twin_a', -6.0)], 2000)
    whole = recipe('twins_docked', [at('twins', 6.0)], 1800)
    cams = [{'name': 'docking_side_right', 'eye': [-31.2, 5.0, 0], 'target': [0, 5.0, 0]},
            {'name': 'docking_side_left', 'eye': [31.2, 5.0, 0], 'target': [0, 5.0, 0]},
            {'name': 'docking_near_right', 'eye': [-20.0, 5.5, 0], 'target': [0, 5.5, 0]},
            {'name': 'docking_quarter', 'eye': [-16.0, 9.0, -14.0], 'target': [0, 5.0, 0]}]
    return split, whole, cams



BODIES = {
    'twin_a': {'name': 'twin_a', 'folder': MODELS/'twin_a', 'dims': A, 'parts': A_PARTS,
               'ranges': RANGES_A,
               'note': "Binary Mechanica's twin A, the 1: the split form's leader (the player's "
                       "inputs); tall and slim, cyan. The combined form's head, torso and arms",
               'guard_note': "a fencer's guard: upright and light, right foot and lead fist "
                             "forward, the rear fist by the chin; both soles on y = 0"},
    'twin_b': {'name': 'twin_b', 'folder': MODELS/'twin_b', 'dims': B, 'parts': B_PARTS,
               'ranges': RANGES_B,
               'note': "Binary Mechanica's twin B, the 0: the split form's partner; short and "
                       "stocky, pink. The combined form's hips and legs",
               'guard_note': "a brawler's guard: low and wide, hunched over the barrel chest, "
                             "both big fists forward; both soles on y = 0"},
    'twins': {'name': 'twins', 'folder': HERE, 'dims': C, 'parts': C_PARTS, 'ranges': RANGES_C,
              'note': "Binary Mechanica's Twins combined: twin A (cyan) above, twin B (pink) "
                      "below; the mech the player picks",
              'guard_note': "the combined guard: planted wide, fists up; both soles on y = 0"},
}
BUDGET = {'twin_a': 1000, 'twin_b': 1000, 'twins': 1800}
STANCES = {'twin_a': (A_STANCE, A_DROP), 'twin_b': (B_STANCE, B_DROP), 'twins': (C_STANCE, C_DROP)}


def main():
    for key in ('twin_a', 'twin_b', 'twins'):
        body = BODIES[key]
        stance, drop = STANCES[key]
        body['height'] = round(height(body), 3)
        if key == 'twins':
            body['extra'] = {'combined_map': combined_map()}
        written = write_body(body, stance, drop, BUDGET[key])
        rig = body_rig(body, stance, drop, written)
        H.write(body['folder']/f'{body["name"]}.rig.json', rig)
        print(f'{key}: {rig["triangles"]} triangles, {body["height"]} m tall')
    split, whole, cams = docking_recipe()
    H.write(HERE/'twins_docking.asset.json', split)
    H.write(HERE/'twins_docked.asset.json', whole)
    H.write(HERE/'cameras_docking.json', cams)
    H.write_emblem(HERE/'binary_emblem.png', emblem_binary())


if __name__ == '__main__':
    main()
