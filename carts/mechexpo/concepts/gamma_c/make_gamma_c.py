#!/usr/bin/env python3
"""Mech Expo 2000: GAMMA (Heartland Atomic, HA-58 proposed), look concept C: military surplus.

Not packed and not in the roster: recipes for concept renders, for the owner to choose a
direction before the real mech is built (they live outside models/, whose every recipe
tools/gen_mechexpo_assets.py packs). Gamma is Heartland's echo of Beam (MOVES.md, "Decided by
the owner (2026-10-14): Gamma, Heartland's ray gun"): Beam's frame on the Hero's skeleton
(../../models/beam/make_beam.py, ../../models/hero/make_hero.py, imported, not copied), the same
part ids, joints and guard, so Beam's keyframes play on it unchanged.

Direction C: Heartland buys surplus and makes it work. This Beam is a field-artillery and
civil-defence unit refitted for the trial: boxy, stencilled, a little battered, like a
decommissioned Cold War vehicle given a second life. Honest working kit, not camouflage.

  head       a searchlight on a yoke: a drum lying fore and aft, its green lens behind a wire
             guard (a cross of bars) under a hood
  torso      a boxy chest; the reactor behind a louvred hatch on the sternum (the green glow
             between three slats, on its front and both sides, so it shows side-on too); a
             primer replacement panel on the left breast; on the back, in place of Beam's
             reaction tanks, a rack carrying two jerrycans (their handles the grab handles)
             under a strap, a toolbox stencilled 58, a pintle hook and a whip antenna
  pauldron   Beam's square blocks, Heartland's roundel on the outer face, the unit number (58)
             stencilled on the front; the right one a replacement in primer, not yet stencilled
  projector  weapon_r, the nuclear ray projector: a searchlight converted to a gun. The
             receiver on the fist, a cooling fin, a slotted barrel shroud (the vents: the gun
             heats while the Atomic Ray runs), the lensed searchlight drum at the muzzle with its
             wire guard and hood, and under the shroud the shrouded tube of the Rod Shot,
             its bore under the lens. The muzzle is Beam's (MUZZLE): the effects need not move
  shield     weapon_l, the lead shield for Lead Shielding: a field gun's armoured plate with a
             bent-back top lip and a sight slit, the trefoil stencilled on it. Stowed it lies
             along the outside of the left forearm; turned 90 degrees about the mount's Y
             (SHIELD_OUT) it swings out on the fist like a door to stand across the arm's line
             in front of the fist, its stencilled face to the other mech; with the forearm
             pointed forward and in, it covers the chest. Beam's left hand was empty, so this
             is the existing mount (weapon_l), no new joint
  the rest   the Hero's pelvis, arms, hands and legs (Beam's), in Heartland's paint: chipped
             paint (primer showing) on the worn edges, a primer replacement shin on the left,
             the HA-58 plate on each thigh

The paint is in roles (the material names), and a scheme gives each role its colour: SCHEMES,
two variants within Heartland's palette (STYLE.md: faded forest green and primer grey, one
neutral metal, one green glow; stencils in off-white). The chosen one paints the poses.

Writes, beside this script: gamma_c_{idle,ray,shield,flare,ground_zero,rest}.asset.json (the
poses, in the chosen scheme), gamma_c_paint_{1,2}.asset.json (the idle in each scheme),
cameras.json and asset-preview.json (the hangar look, as the mechs'). render_gamma_c.py renders
them beside Beam, Tank and the Hero and draws the sheets.
Run from anywhere: python3 carts/mechexpo/concepts/gamma_c/make_gamma_c.py (standard library
only).
"""
import copy
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parents[1]/'models'
for sub in ('hero', 'beam', 'tank'):
    sys.path.insert(0, str(MODELS/sub))
import make_hero as H  # noqa: E402
import make_beam as B  # noqa: E402
import make_tank as TK  # noqa: E402
import mxpaint as P  # noqa: E402

T, loft, crect, by_side, box = H.T, H.loft, H.crect, H.by_side, H.box
cyl_y, cyl_z = B.cyl_y, B.cyl_z

P.FONT.setdefault('8', ['01110', '10001', '10001', '01110', '10001', '10001', '01110'])

# ---- paint ------------------------------------------------------------------------------------
# Heartland's colours (make_tank.py): the greens, primer, one neutral metal (gunmetal), the dark
# of rubber and bores, the stencils' off-white, and the reactor's green glow.

BASE = {
    'green': TK.GREEN, 'green_dk': TK.GREEN_DK, 'primer': TK.PRIMER, 'gun': TK.GUN,
    'dark': TK.DARK, 'cream': TK.CREAM,
}
GLOW = '#8cff6e'

# The roles: what each surface is. A scheme maps every role to a base colour.
#   hull     the main armour            hull2   the second tone (colour blocking)
#   patch    replacement panels          worn    the hull, chipped (texture: `chip` showing)
#   frame    joints, frame, the gun's metal
#   can      the jerrycans               kit     the toolbox
#   plate    the lead shield             ink     the stencils
ROLES = ['hull', 'hull2', 'patch', 'frame', 'can', 'kit', 'plate', 'ink', 'chip']

SCHEME_1 = {'hull': 'green', 'hull2': 'green_dk', 'patch': 'primer', 'frame': 'gun',
            'can': 'green_dk', 'kit': 'primer', 'plate': 'green_dk', 'ink': 'cream',
            'chip': 'primer'}
# Scheme 2: the unit stripped and primed at the depot, a few original green panels left on
# (the replacements, here, are the old green ones), the cans and toolbox in green.
SCHEME_2 = {'hull': 'primer', 'hull2': 'green_dk', 'patch': 'green', 'frame': 'gun',
            'can': 'green', 'kit': 'green_dk', 'plate': 'green_dk', 'ink': 'cream',
            'chip': 'gun'}
SCHEMES = {'1': ('Depot green', SCHEME_1), '2': ('Primer refit', SCHEME_2)}
CHOSEN = '1'
SERIAL = 'HA-58'


def stencil(text, field, ink, w=32, h=16, px=2):
    """`text` in the plate font at `px` texels a pixel, centred on `field`: a stencilled number."""
    tw = (len(text)*6-1)*px
    x0, y0 = (w-tw)//2, (h-7*px)//2
    return P.texels(P.text_shapes(text, x0/w, y0/h, px/w, px/h, ink), w, h, field, ss=1)


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


def jerrycan(field, line, w=24, h=32):
    """A jerrycan's side: the pressed X and its border, in `line` on `field`."""
    def bar(a, b, t):
        dx, dy = b[0]-a[0], b[1]-a[1]
        ln = math.hypot(dx, dy)
        px, py = -dy/ln*t/2, dx/ln*t/2
        return ('poly', line, [(a[0]+px, a[1]+py), (b[0]+px, b[1]+py), (b[0]-px, b[1]-py),
                               (a[0]-px, a[1]-py)])
    s = [('poly', line, [(0.1, 0.08), (0.9, 0.08), (0.9, 0.92), (0.1, 0.92)]),
         ('poly', field, [(0.16, 0.12), (0.84, 0.12), (0.84, 0.88), (0.16, 0.88)]),
         bar((0.2, 0.16), (0.8, 0.84), 0.07), bar((0.8, 0.16), (0.2, 0.84), 0.07)]
    return P.texels(s, w, h, field)


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


def materials(scheme):
    c = {role: BASE[scheme[role]] for role in ROLES}
    m = {role: {'color': c[role]} for role in ROLES if role not in ('ink', 'chip')}
    m['dark'] = {'color': BASE['dark']}
    m['glow'] = {'color': GLOW, 'class': 'emissive'}
    m['worn'] = {'color': c['hull'], 'texture': {**chips(c['hull'], c['chip']),
                                                 'projection': 'box', 'scale': [1.5, 1.5]}}
    m['vents'] = {'color': c['frame'], 'texture': {**slots(c['frame'], BASE['dark']),
                                                   'projection': 'cylindrical',
                                                   'scale': [0.42, 0.42]}}
    for key, field in (('roundel', c['hull']), ('roundel_p', c['patch'])):
        dark = BASE['green_dk'] if field != BASE['green_dk'] else BASE['dark']
        m[key] = {'color': field, 'texture': {
            **H.emblem_texture(TK.emblem_heartland(green=field, cream=BASE['cream'], dark=dark,
                                                   glow=GLOW), field), 'projection': 'fit'}}
    for key, field in (('unit', c['hull']), ('unit_k', c['kit'])):
        m[key] = {'color': field, 'texture': {**stencil('58', field, c['ink']),
                                              'projection': 'fit'}}
    m['serial'] = {'color': BASE['primer'], 'texture': {
        **P.serial_plate(SERIAL, BASE['primer'], BASE['dark']), 'projection': 'fit'}}
    m['jerry'] = {'color': c['can'], 'texture': {**jerrycan(c['can'], c['frame']),
                                                 'projection': 'fit'}}
    m['trefoil'] = {'color': c['plate'], 'texture': {**trefoil(c['plate'], c['ink']),
                                                     'projection': 'fit'}}
    return m


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


# ---- the parts (left / centre, origin at the joint) --------------------------------------------

def head(side=None):
    """A searchlight on a yoke. The drum lies fore and aft (its axis Z), its front cap the green
    lens behind a wire guard (two upright bars and a crossbar) under a hood that juts like a
    brow, on a yoke whose arms hold it either side."""
    neck = cyl_y('neck', 0.34, 0.5, 4, 'frame', [0, 0.16, 0])
    yoke = box('yoke', [1.42, 0.2, 0.7], 'hull2', [0, 0.38, 0.0])
    arms = group('yoke_arms', [box('yoke_arm', [0.14, 0.62, 0.34], 'hull2', [0.68, 0.7, 0.0])],
                 mirror=True)
    # the drum; its front cap is the lens's rim, the lens a thinner drum standing out of it
    lamp = cyl_z('lamp', 0.6, 1.16, 8, 'hull', [0, 0.92, 0.02],
                 faces={'bottom': 'frame', 'top': 'frame'})
    lens = cyl_z('lens', 0.46, 0.16, 8, 'frame', [0, 0.92, -0.58], faces={'bottom': 'glow'})
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


def by_id(nodes, id_):
    return next(n for n in nodes if n['id'] == id_)


def back_rack():
    """In place of Beam's reaction tanks: a rack on the back, two jerrycans strapped to it
    (their pressed X on the outer faces, a handle on each), a toolbox under them stencilled
    with the unit number, a pintle hook under the toolbox and the whip antenna."""
    rack = box('rack', [2.1, 2.3, 0.32], 'frame', [0, 2.3, 1.12])
    can = group('cans', [group('can', [
        box('can_body', [0.5, 1.5, 1.08], 'can', [0, 0, 0],
            faces={'right': 'jerry', 'left': 'jerry'}),
        # the three-bar handle on top: a grab handle too
        box('can_handle', [0.22, 0.16, 0.6], 'frame', [0, 0.8, 0.08]),
    ], [0.54, 2.74, 1.8])], mirror=True)
    strap = box('strap', [1.68, 0.12, 1.16], 'dark', [0, 2.46, 1.8])
    toolbox = box('toolbox', [1.9, 0.62, 0.9], 'kit', [0, 1.72, 1.66],
                  faces={'top': 'hull2', 'front': 'unit_k'})
    # the pintle hook under the toolbox, its jaw turned back
    hook = box('pintle', [0.2, 0.56, 0.2], 'frame', [0, 1.24, 1.86], [-30, 0, 0])
    # the whip: its base on the rack's top right corner, the rod raked back
    whip = group('whip', [box('whip_rod', [0.08, 3.9, 0.08], 'dark', [0, 1.75, 0])],
                 [-0.86, 3.4, 1.18], [16, 0, 0])
    return [rack, can, strap, toolbox, hook, whip]


def pauldron(side=None):
    """Beam's square block, Heartland's roundel on the outer face (the middle band's +X side,
    flat); the right one is a replacement in primer; a chipped top."""
    face = 'patch' if side == 'r' else 'hull'
    mark = 'roundel_p' if side == 'r' else 'roundel'
    plate = loft('plate', 'y', [
        (0.92, crect(0.56, 0.62, 0.12, 0.12, ox=0.26)),
        (0.44, crect(0.94, 1.0, 0.18, 0.18, ox=0.44)),
        (-0.44, crect(0.94, 1.0, 0.18, 0.18, ox=0.44)),
        (-0.68, crect(0.80, 0.86, 0.16, 0.16, ox=0.46)),
    ], by_side({0: {'*': 'worn' if side != 'r' else face},
                1: {'*': face, 'r': mark, 'f': 'unit' if side != 'r' else 'hull2',
                    'b': 'hull2'},
                2: {'*': 'hull2'}}),
        'frame', face)
    return [plate]


MUZZLE = B.MUZZLE           # (0, 0.8, -4.4): Beam's, so the effects start where they did
ROD = (0.0, 0.3, -4.86)     # the Rod Shot's bore, under the lens


def projector(side=None):
    """The nuclear ray projector (weapon_r), on Beam's mount and held as Beam holds the Arc
    Cannon: the grip up through the fist, the receiver on top, the barrel along -Z (the
    forearm's line). From the fist out: the receiver and a cooling fin, the slotted shroud, the
    searchlight drum with the lens at MUZZLE behind its wire guard, and the Rod Shot's tube."""
    y = MUZZLE[1]
    body = box('receiver', [1.0, 0.92, 1.9], 'hull', [0, y, -0.35],
               faces={'top': 'worn', 'front': 'hull2', 'back': 'hull2'})
    # a cooling fin round the shroud's root, and the shroud itself slotted for the vents
    fins = [cyl_z(f'fin_{k}', 0.62, 0.12, 6, 'frame', [0, y, z]) for k, z in
            enumerate((-1.5,))]
    shroud = cyl_z('shroud', 0.4, 2.3, 8, 'vents', [0, y, -2.35])
    # the searchlight drum, its front cap the lens's rim, the lens standing out of it at MUZZLE
    drum = cyl_z('drum', 0.92, 1.04, 8, 'hull', [0, y, MUZZLE[2]+0.62],
                 faces={'bottom': 'frame', 'top': 'hull2'})
    lens = cyl_z('lens', 0.72, 0.16, 8, 'frame', [0, y, MUZZLE[2]+0.08], faces={'bottom': 'glow'})
    hood = box('drum_hood', [1.8, 0.18, 0.9], 'hull2', [0, y+0.9, MUZZLE[2]+0.36], [-6, 0, 0])
    bars = [box('lens_bar', [0.09, 1.6, 0.09], 'frame', [0, y, MUZZLE[2]-0.18]),
            box('lens_cross', [1.6, 0.09, 0.09], 'frame', [0, y, MUZZLE[2]-0.26])]
    # the Rod Shot: a tube under the shroud in a jacket of its own, through the drum, its bore
    # standing out under the lens
    tube = cyl_z('rod_tube', 0.16, 4.1, 6, 'frame', [0, ROD[1], ROD[2]+2.05],
                 faces={'bottom': 'dark'})
    jacket = box('rod_jacket', [0.42, 0.34, 1.9], 'hull2', [0, ROD[1], -2.2])
    return [body, *fins, shroud, drum, lens, hood, *bars, tube, jacket]


SHIELD_OUT = [0, 90, 0]      # weapon_l's key that swings the shield out in front of the fist


def shield(side=None):
    """The lead shield (weapon_l). Mount frame: +Y out of the fist's thumb side (up, with the
    forearm level), -Z along the forearm past the fist, +Z back toward the elbow, +X outward. The
    plate stands in the Y-Z plane outside the hand and forearm (stowed); a bracket holds it to
    the back of the fist. Turned SHIELD_OUT about Y it stands across the arm's line 0.7 m in
    front of the grip, its front face (the trefoil) looking along the forearm."""
    # a field gun's shield: an upright plate, its upper corners cut, and a lip bent back along
    # its top (seen side-on when it is braced: the hook at the top)
    outline = [(-0.72, -1.15), (1.86, -1.15), (1.86, 0.82), (1.56, 1.12), (-0.42, 1.12),
               (-0.72, 0.82)]
    plate = plate_x('plate', outline, 0.18, 'plate', [0.7, 0, 0],
                    faces={'side': 'frame'},
                    decals=[{'id': 'mark', 'face': 'front', 'material': 'trefoil',
                             'size': [1.1, 1.1], 'at': [0.62, -0.18]},
                            {'id': 'slit', 'face': 'front', 'material': 'dark',
                             'size': [0.9, 0.12], 'at': [0.45, 0.78]}])
    lip = plate_x('lip', [(-0.42, 0.0), (1.56, 0.0), (1.56, 0.36), (-0.42, 0.36)], 0.14, 'plate',
                  [0.7, 1.08, 0], [0, 0, 50], faces={'side': 'frame'})
    bracket = box('bracket', [0.3, 0.6, 0.5], 'frame', [0.53, 0, 0.18])
    return [plate, lip, bracket]


def shared(part):
    return lambda side=None: hero_nodes(part, side)


PARTS = {
    'pelvis': shared('pelvis'), 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': shared('upper_arm'), 'forearm': shared('forearm'), 'hand': shared('hand'),
    'projector': projector, 'shield': shield,
    'thigh': shared('thigh'), 'shin': shared('shin'), 'foot': shared('foot'),
}
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


def recipe(name, nodes, scheme, budget=1950):
    mats = materials(scheme)
    r = H.recipe(name, nodes, budget, 2048, materials=mats)
    r['materials'] = {k: v for k, v in mats.items() if k in used(nodes)}
    r['lighting'] = LIGHTING
    return r


# ---- posing ----------------------------------------------------------------------------------

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


def arm_point(stance, side, local):
    """A point given in a hand's weapon frame (its mount's, turned by its key), in the torso's
    frame, for the arm angles in `stance`."""
    sx = -1 if side == 'r' else 1
    sh = [sx*H.SHOULDER[0], H.SHOULDER[1], H.SHOULDER[2]]

    def st(n):
        return H.rot(stance.get(f'{n}_{side}', [0, 0, 0]))
    ru = st('upper_arm')
    elbow = H.add(sh, H.mv(ru, [0, -H.UPPER, 0]))
    rf = H.mm(ru, st('forearm'))
    wrist = H.add(elbow, H.mv(rf, [0, -H.FORE, 0]))
    rh = H.mm(rf, st('hand'))
    grip = H.add(wrist, H.mv(rh, [0, H.GRIP, 0]))
    rw = H.mm(rh, H.mm(H.rot(H.MOUNT_ROTATE), st('weapon')))
    return H.add(grip, H.mv(rw, list(local)))


def solve_arm(side, point, local=(0.0, H.GRIP, 0.0), aligns=(), base=None, elbow_out=1.4):
    """Shoulder, elbow and wrist angles (in the torso's frame) that put the hand's `local` point
    at `point` and turn each hand vector of `aligns` [(local, wanted), ...] toward its wanted
    direction, within Beam's joint ranges (MOVES.md). A right arm is the left one mirrored."""
    def mir(v):
        return [-v[0], v[1], v[2]]
    if side == 'r':
        point = mir(point)
        aligns = [(mir(a), mir(b)) for a, b in aligns]
    sh = list(H.SHOULDER)
    # Beam's ranges; its moves turn neither arm about Y, so neither does this
    lim = [(-60, 170), (0, 0), (-10, 80), (0, 140), (0, 0), (-60, 60), (0, 0), (-30, 30)]

    def cost(p):
        ru = H.rot(p[0:3])
        elbow = H.add(sh, H.mv(ru, [0, -H.UPPER, 0]))
        rf = H.mm(ru, H.rot([p[3], p[4], 0]))
        wrist = H.add(elbow, H.mv(rf, [0, -H.FORE, 0]))
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
    p = list(base or [20.0, 0.0, 10.0, 90.0, 0.0, 0.0, 0.0, 0.0])
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
        out = {k: [v[0], -v[1], -v[2]] for k, v in out.items()}
    return {f'{k}_{side}': v for k, v in out.items()}


def poses():
    """{name: (stance, drop)}: every pose solved so both soles sit on the floor."""
    out = {}
    # Idle: Beam's guard exactly (its planted stance, the projector level at the other mech, the
    # left fist up under it), the shield stowed along the left forearm.
    out['idle'] = (dict(B.STANCE), B.DROP)

    # The Atomic Ray, held: dug in against the push, lower and wider, leaning into the gun; the
    # projector raised level at chest height, the left fist pulled back to the hip.
    drop = 1.0
    st = {'pelvis': [0, -10, 0], 'torso': [-10, -14, 0], 'head': [8, 16, 0],
          'thigh_r': [34, 0, -12], 'thigh_l': [-26, 0, 12],
          'upper_arm_r': [40, 0, -8], 'forearm_r': [52, 0, 6], 'hand_r': [-2, 0, 0],
          'upper_arm_l': [-34, 0, 16], 'forearm_l': [104, 0, 0], 'hand_l': [-10, 0, 0]}
    out['ray'] = (H.pose(st, drop), drop)

    # Lead Shielding: crouched low behind the shield, swung out in front of the left fist; the
    # body turned left side forward, the left forearm pointed at the other mech, the thumb up;
    # the projector drawn back level at the hip.
    drop = 1.05
    st = {'pelvis': [0, 8, 0], 'torso': [-22, 26, 0], 'head': [18, -26, 0],
          'thigh_r': [30, 0, -22], 'thigh_l': [-14, 0, 22],
          'weapon_l': list(SHIELD_OUT),
          'upper_arm_r': [-16, 0, -14], 'forearm_r': [96, 0, 6], 'hand_r': [6, 0, 0]}
    st.update(solve_arm('l', [0.5, 2.6, -3.2], aligns=[((0, -1, 0), [-0.1, 0, -1]),
                                                       ((0, 0, -1), [0, 1, 0])],
                        base=[70, 0, 0, 30, 0, 0, 0, 0], elbow_out=0.5))
    out['shield'] = (H.pose(st, drop), drop)

    # Geiger Flare: the projector thrown up at the sky ahead, the body leaning back under it,
    # the head up with it; the left arm braced low with the shield.
    drop = 0.7
    st = {'pelvis': [0, -6, 0], 'torso': [10, -10, 0], 'head': [22, 10, 0],
          'thigh_r': [24, 0, -10], 'thigh_l': [-16, 0, 10],
          'upper_arm_r': [150, 0, -8], 'forearm_r': [20, 0, 0], 'hand_r': [0, 0, 0],
          'upper_arm_l': [20, 0, 14], 'forearm_l': [70, 0, -10], 'hand_l': [0, 0, 0]}
    out['flare'] = (H.pose(st, drop), drop)

    # Ground Zero: planted wide and low, the chest thrown open (the reactor bared), the head
    # back, the projector driven muzzle-down at the floor ahead and out, the left arm flung
    # out behind.
    drop = 1.1
    st = {'pelvis': [0, 0, 0], 'torso': [16, 0, 0], 'head': [24, 0, 0],
          'thigh_r': [12, 0, -24], 'thigh_l': [-8, 0, 24],
          'upper_arm_r': [22, 0, -38], 'forearm_r': [6, 0, 0], 'hand_r': [-30, 0, 0],
          'upper_arm_l': [-36, 0, 58], 'forearm_l': [24, 0, 0], 'hand_l': [-10, 0, 0]}
    out['ground_zero'] = (H.pose(st, drop), drop)
    return out


# ---- cameras ---------------------------------------------------------------------------------

def aim(name, centre, d, dist):
    ln = math.sqrt(H.dot(d, d))
    return {'name': name, 'eye': [round(centre[k]+d[k]*dist/ln, 3) for k in range(3)],
            'target': [round(c, 3) for c in centre]}


def cameras(ps):
    """The fight's side view at game distance (31.2 m: the mech about 80 px of 240), a nearer side
    view, three-quarters from the front and the back, and the halves of fight frames: this mech
    7 m left of centre facing right, the other 7 m right facing left; and closer (22 m, the
    camera zoomed in as the mechs meet), 5.5 m either side. Then close-ups: the head and the
    reactor hatch in the rest pose (nothing in front of them), the projector and the stowed
    shield in the idle, the shield swung out in Lead Shielding."""
    cams = [
        {'name': 'side', 'eye': [-31.2, 5.8, -2.0], 'target': [0, 5.8, -2.0]},
        {'name': 'side_near', 'eye': [-21.0, 7.6, -2.0], 'target': [0, 7.6, -2.0]},
        {'name': 'side_near_l', 'eye': [21.0, 7.6, -2.0], 'target': [0, 7.6, -2.0]},
        {'name': 'three_quarter', 'eye': [-13.0, 10.0, -16.5], 'target': [0, 7.6, -1.0]},
        {'name': 'back_quarter', 'eye': [12.5, 10.5, 15.5], 'target': [0, 7.6, 0.5]},
        {'name': 'front', 'eye': [0, 8.6, -21.0], 'target': [0, 7.6, 0]},
        {'name': 'fight_left', 'eye': [-31.2, 5.8, -7.0], 'target': [0, 5.8, -7.0]},
        {'name': 'fight_right', 'eye': [31.2, 5.8, -7.0], 'target': [0, 5.8, -7.0]},
        {'name': 'close_left', 'eye': [-22.0, 6.4, -5.5], 'target': [0, 6.4, -5.5]},
        {'name': 'close_right', 'eye': [22.0, 6.4, -5.5], 'target': [0, 6.4, -5.5]},
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
    idle, drop = ps['idle']
    fr = frames(idle, drop)
    wr, wp = fr['weapon_r']
    gc = H.add(wp, H.mv(wr, [0, 0.8, -2.0]))
    cams += [aim('gun_side', gc, [-1, 0.2, 0.05], 6.0),
             aim('gun_quarter', gc, [-0.7, 0.35, -0.8], 6.0)]
    lr, lp = fr['weapon_l']
    sc = H.add(lp, H.mv(lr, [0.7, 0, 0.57]))
    cams += [aim('shield_stowed', sc, [1, 0.2, -0.3], 5.5)]
    st, drop = ps['shield']
    fr = frames(st, drop)
    lr, lp = fr['weapon_l']
    sc = H.add(lp, H.mv(lr, [0.7, 0, 0.57]))
    cams += [aim('shield_front', sc, [-0.35, 0.2, -1], 8.0),
             aim('shield_quarter', sc, [-1, 0.3, -0.6], 8.0)]
    return cams


def muzzle_world(stance, drop):
    """MUZZLE and the barrel's direction in the asset's frame, for a pose (the renderer's ray)."""
    r, p = frames(stance, drop)['weapon_r']
    return H.add(p, H.mv(r, list(MUZZLE))), H.mv(r, [0, 0, -1])


def main():
    chosen = SCHEMES[CHOSEN][1]
    ps = poses()
    for name, (st, drop) in ps.items():
        H.write(HERE/f'gamma_c_{name}.asset.json',
                recipe(f'gamma_c_{name}', assemble(st, drop), chosen))
    st, drop = ps['idle']
    for k, (_, scheme) in SCHEMES.items():
        H.write(HERE/f'gamma_c_paint_{k}.asset.json',
                recipe(f'gamma_c_paint_{k}', assemble(st, drop), scheme))
    H.write(HERE/'gamma_c_rest.asset.json', recipe('gamma_c_rest', assemble({}, 0.0), chosen))
    H.write(HERE/'cameras.json', cameras(ps))
    H.write(HERE/'asset-preview.json', LOOK)


if __name__ == '__main__':
    main()
