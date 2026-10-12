#!/usr/bin/env python3
"""Mech Expo 2000: Beam (Raikō Chemical Group), the zoner.

Raikō's base mech on the shared skeleton: the Hero's part ids and joints (../hero/make_hero.py,
imported, not copied), so poses carry from one mech to the other and the Animation Kit reads it
the same way. The armour is Raikō's own; the limbs that are plain machinery are the Hero's,
repainted. Raikō is yellow, with charcoal plates, copper coils, gunmetal joints and one glow:
the green of the reaction (the visor and the back tanks).

  head      a square helmet with a green visor slit under a brim, copper coils at the temples
            and a raked antenna (the lightning rod) that makes the profile
  torso     a broad, square chest; on the back a frame carrying two upright reaction tanks that
            glow green (the chemical power source), read from the side as a hump
  pauldron  big square shoulder blocks, Raikō's mark on the outer face
  cannon    the Raikō Arc Cannon (weapon_r): a pistol-gripped capacitor body on the fist, the
            barrel along the forearm's line (the weapon's -Z), two copper coils and a glowing
            muzzle 4.4 m ahead of the grip. The left hand is empty (no weapon_l)
  the rest  the Hero's pelvis, arms, hands, thighs, shins and feet, in Raikō's paint; a serial
            plate on each thigh (RC-03) and yellow-and-black hazard stripes round the ankles

Writes, beside this script: beam.asset.json (assembled, in its guard), beam_rest.asset.json (the
rest pose), beam_flex.asset.json (every joint bent far, for checking; not packed),
parts/beam_*.asset.json (each part alone, its origin at its joint), beam.rig.json, cameras.json,
cameras_flex.json and raiko_emblem.png (the mark for the menus).
Run from anywhere: python3 carts/mechexpo/models/beam/make_beam.py
Standard library only.
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'hero'))
import make_hero as H  # noqa: E402
import mxpaint as P  # noqa: E402

loft, crect, by_side, cyl_x, box, T = H.loft, H.crect, H.by_side, H.cyl_x, H.box, H.T

# ---- Raikō's mark and the serial plate's glyphs ---------------------------------------------

RAIKO_YELLOW, RAIKO_BLACK = '#f5c21b', '#2a2c31'

# the plate's 5 x 7 font has no C or 3 (mxpaint.py draws only the glyphs the plates use)
P.FONT.setdefault('C', ['01110', '10001', '10000', '10000', '10000', '10001', '01110'])
P.FONT.setdefault('3', ['11110', '00001', '00001', '01110', '00001', '00001', '11110'])


def emblem_raiko(yellow=RAIKO_YELLOW, black=RAIKO_BLACK):
    """Raikō Chemical Group: a hexagon (a benzene ring: chemistry) with a lightning bolt struck
    through it (raikō, a lightning flash). A yellow hexagon, a black field inside a yellow ring,
    and the bolt in yellow running from top right to bottom left past the ring."""
    import math

    def hexagon(r):
        return [(0.5+r*math.cos(math.radians(30+60*k)), 0.5+r*math.sin(math.radians(30+60*k)))
                for k in range(6)]
    bolt = [(0.66, 0.04), (0.36, 0.50), (0.52, 0.50), (0.32, 0.96), (0.72, 0.42), (0.55, 0.42),
            (0.80, 0.04)]
    return [('poly', yellow, hexagon(0.5)), ('poly', black, hexagon(0.42)),
            ('poly', yellow, hexagon(0.33)), ('poly', black, hexagon(0.26)),
            ('poly', black, [(x+0.03, y) for x, y in bolt]), ('poly', yellow, bolt)]


# ---- paint (STYLE.md: Raikō is yellow; one glow) --------------------------------------------

MATERIALS = {
    'yellow':   {'color': RAIKO_YELLOW},
    'black':    {'color': RAIKO_BLACK},              # charcoal plates
    'copper':   {'color': '#c8783a', 'smooth': True},  # the coils
    'metal':    {'color': '#8e959f', 'smooth': True},  # gunmetal: Raikō's chrome
    'frame':    {'color': '#4a4f58'},                # joints, frame
    'dark':     {'color': '#1c1d21'},
    'gglow':    {'color': '#b4ff3c', 'class': 'emissive'},   # the reaction's green: visor, tanks, muzzle
    'emblem':   {'color': RAIKO_BLACK, 'texture': {
        **P.texels(P.scaled(emblem_raiko(), 28/56, 28/32, 14/56, 2/32), 56, 32, RAIKO_BLACK),
        'projection': 'fit'}},
    'serial':   {'color': RAIKO_YELLOW, 'texture': {**P.serial_plate('RC-03', RAIKO_YELLOW, RAIKO_BLACK),
                                                    'projection': 'fit'}},
    'hazard':   {'color': RAIKO_YELLOW, 'texture': {**P.hazard([RAIKO_YELLOW, '#1c1d21']),
                                                    'projection': 'box', 'scale': [0.32, 0.32]}},
}

# The Hero's material -> Raikō's, for every part taken from the Hero; PER_NODE by node id.
PAINT = {'red': 'yellow', 'white': 'black', 'chrome': 'metal', 'frame': 'frame', 'dark': 'dark',
         'glow': 'gglow', 'steel': 'metal', 'edge': 'gglow'}
PER_NODE = {
    'skirt': {'chrome': 'black', 'red': 'yellow'},          # the side skirts
    'gauntlet': {'white': 'yellow', 'chrome': 'black'},     # forearm: yellow, a charcoal cuff
    'knee_guard': {'white': 'black'},
    'back': {'red': 'black'},                               # the backs of the hands
    'thumb': {'red': 'black'},
    'instep': {'white': 'black'},
}


def repaint(nodes):
    """A deep copy of the Hero's nodes in Raikō's paint."""
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
    return repaint([n for n in H.PARTS[part]() if n['id'] not in drop])


def by_id(nodes, id_):
    return next(n for n in nodes if n['id'] == id_)


def cyl_y(id_, r, h, seg, mat, at, faces=None):
    n = {'id': id_, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': seg,
         'material': mat, 'transform': T(at)}
    if faces:
        n['faces'] = faces
    return n


def cyl_z(id_, r, h, seg, mat, at, faces=None):
    """A drum along Z (the cannon's barrel and coils)."""
    n = {'id': id_, 'op': 'cylinder', 'radius': r, 'height': h, 'segments': seg,
         'material': mat, 'transform': T(at, [90, 0, 0])}
    if faces:
        n['faces'] = faces
    return n


# ---- Raikō's pieces ---------------------------------------------------------------------------

def head():
    """Square and low under a brim, a green slit of a visor, copper coils at the temples and a
    raked antenna rising from the back of the crown: the lightning rod, the profile's mark."""
    neck = cyl_y('neck', 0.34, 0.6, 4, 'frame', [0, 0.2, 0])   # under the collar
    helmet = loft('helmet', 'y', [
        (0.28, crect(0.52, 0.54, 0.12, 0.10)),
        (0.62, crect(0.66, 0.66, 0.16, 0.12, oz=-0.02)),
        (0.86, crect(0.68, 0.68, 0.16, 0.12, oz=-0.02)),
        (1.22, crect(0.62, 0.62, 0.14, 0.12)),
        (1.38, crect(0.44, 0.46, 0.10, 0.10, oz=0.02)),
    ], by_side({0: {'*': 'black', 'f': 'dark', 'fr': 'dark', 'fl': 'dark'},
                1: {'*': 'yellow', 'f': 'gglow', 'fr': 'gglow', 'fl': 'gglow'},
                2: {'*': 'yellow'},
                3: {'*': 'black'}}),
        'frame', 'black')
    # the brim over the visor: a wedge across the face, jutting forward
    brim = H.chevron('brim', 'black',
                     [(-0.6, 0.86), (-0.98, 0.9), (-0.9, 1.02), (-0.56, 1.14)],
                     [(-0.6, 0.88), (-0.84, 0.92), (-0.8, 1.0), (-0.58, 1.08)], 0.66)
    jaw = H.chevron('jaw', 'metal',
                    [(-0.5, 0.3), (-0.8, 0.34), (-0.84, 0.52), (-0.54, 0.6)],
                    [(-0.5, 0.32), (-0.68, 0.36), (-0.7, 0.5), (-0.54, 0.58)], 0.48)
    # the antenna: a raked spike from the crown's back, yellow with a copper tip band
    rod = [(0.0, 1.3), (0.42, 1.3), (1.0, 2.62), (0.82, 2.7)]
    antenna = loft('antenna', 'x', [(-0.08, rod), (0.08, rod)],
                   lambda k, j: 'copper' if j == 2 else 'yellow', 'yellow', 'yellow')
    coils = cyl_x('coils', 0.3, 1.5, 6, 'copper', [0, 0.76, 0.12],
                  faces={'top': 'black', 'bottom': 'black'})
    return [neck, helmet, brim, jaw, antenna, coils]


TANK_X, TANK_Z = 0.62, 1.78


def torso():
    """A broad, square chest; the Hero's waist; the reaction tanks on a back frame."""
    hero = hero_nodes('torso', drop=('flywheel', 'hub', 'chest', 'collar', 'pack_mount'))
    chest = loft('chest', 'y', [
        (0.9, crect(1.05, 0.74, 0.26, 0.22)),
        (1.7, crect(1.62, 1.02, 0.36, 0.28, oz=-0.06)),
        (2.5, crect(1.86, 1.12, 0.40, 0.30, oz=-0.08)),
        (3.08, crect(1.74, 1.04, 0.38, 0.28, oz=-0.04)),
        (3.42, crect(1.08, 0.80, 0.26, 0.22, oz=0.02)),
    ], by_side({0: {'*': 'black'},
                1: {'*': 'yellow', 'fr': 'black', 'fl': 'black'},
                2: {'*': 'yellow', 'r': 'black', 'l': 'black'},
                3: {'*': 'metal'}}),
        'frame', 'frame')
    collar = loft('collar', 'y', [
        (3.3, crect(0.74, 0.58, 0.18)),
        (3.66, crect(0.58, 0.46, 0.14)),
    ], lambda k, j: 'black', None, 'frame')
    frame = box('tank_frame', [1.9, 2.0, 0.5], 'frame', [0, 2.15, 1.2])
    # the reaction tanks: green glass cylinders under yellow caps, standing on the frame's foot
    tanks = {'id': 'tanks', 'op': 'group', 'children': [
        cyl_y('tank', 0.44, 1.7, 6, 'gglow', [TANK_X, 2.15, TANK_Z]),
        cyl_y('tank_cap', 0.52, 0.42, 6, 'yellow', [TANK_X, 3.06, TANK_Z],
              faces={'top': 'black'})],
        'modifiers': [{'op': 'mirror', 'axis': 'x'}]}
    return [by_id(hero, 'abdomen'), chest, by_id(hero, 'shoulder_sockets'), collar, frame, tanks]


def pauldron():
    """A big square block; its outer face (the middle band's +X side, flat: the same x and z at
    both its sections) carries Raikō's mark."""
    plate = loft('plate', 'y', [
        (0.92, crect(0.56, 0.62, 0.16, 0.16, ox=0.26)),
        (0.44, crect(0.94, 1.0, 0.26, 0.24, ox=0.44)),
        (-0.44, crect(0.94, 1.0, 0.26, 0.24, ox=0.44)),
        (-0.68, crect(0.80, 0.86, 0.22, 0.2, ox=0.46)),
    ], by_side({0: {'*': 'yellow'}, 1: {'*': 'yellow', 'r': 'emblem', 'f': 'black', 'b': 'black'},
                2: {'*': 'black'}}),
        'frame', 'yellow')
    return [plate]




MUZZLE = (0.0, 0.8, -4.4)     # the cannon's muzzle in weapon_r's frame (effects start here)


def cannon():
    """The Raikō Arc Cannon. Local frame as any weapon (the grip's middle at the origin, the grip
    along Y), but a gun: the grip runs up through the fist (+Y the thumb side), the capacitor body
    sits on top of the fist and the barrel runs along -Z, the forearm's line, so a forearm held
    level points it at the other mech. The muzzle is MUZZLE."""
    body = loft('body', 'z', [
        (0.6, crect(0.36, 0.30, 0.10, 0.10, oz=0.76)),
        (0.25, crect(0.50, 0.46, 0.16, 0.16, oz=0.8)),
        (-1.05, crect(0.50, 0.46, 0.16, 0.16, oz=0.8)),
        (-1.4, crect(0.38, 0.36, 0.12, 0.12, oz=0.8)),
    ], by_side({0: {'*': 'black'}, 1: {'*': 'yellow', 'b': 'black', 'br': 'black', 'bl': 'black'},
                2: {'*': 'black'}}),
        'black', 'black')
    # under the barrel, ahead of the fist: the battery cell (a green window on each side)
    cell = box('cell', [0.62, 0.5, 1.0], 'black', [0, 0.16, -0.86], faces={'left': 'gglow', 'right': 'gglow'})
    barrel = cyl_z('barrel', 0.3, 3.0, 6, 'metal', [0, MUZZLE[1], -2.8])
    coils = [cyl_z(f'coil_{k}', 0.5, 0.28, 6, 'copper', [0, MUZZLE[1], z]) for k, z in
             enumerate((-2.0, -3.1))]
    muzzle = cyl_z('muzzle', 0.44, 0.44, 6, 'black', [0, MUZZLE[1], MUZZLE[2]+0.2],
                   faces={'bottom': 'gglow'})
    return [body, cell, barrel, *coils, muzzle]


def shared(part):
    return lambda: hero_nodes(part)


PARTS = {
    'pelvis': shared('pelvis'), 'torso': torso, 'head': head, 'pauldron': pauldron,
    'upper_arm': shared('upper_arm'), 'forearm': shared('forearm'), 'hand': shared('hand'),
    'cannon': cannon, 'thigh': shared('thigh'), 'shin': shared('shin'), 'foot': shared('foot'),
}
WEAPONS = {'r': 'cannon'}

# ---- the guard: planted wide, the cannon level at the other mech, the left fist under it ------

DROP = 0.5
STANCE = H.pose({
    'pelvis': [0, -6, 0],
    'torso': [-4, -6, 0],
    'head': [4, 10, 0],
    'thigh_r': [22, 0, -9], 'thigh_l': [-14, 0, 9],
    'upper_arm_r': [2, 0, -10], 'forearm_r': [86, 0, 8], 'hand_r': [2, 0, 0],
    'upper_arm_l': [18, 0, 12], 'forearm_l': [96, 0, -24], 'hand_l': [-10, 0, 0],
}, DROP)
DRAWN_DROP = DROP


def main():
    H.write_mech(HERE, 'beam', STANCE, DRAWN_DROP, PARTS, H.SIDED, WEAPONS, MATERIALS)
    views = (('head_front', [0, 0.3, -1]), ('head_side_right', [-1, 0.25, 0]),
             ('head_side_left', [1, 0.25, 0]), ('head_three_quarter', [-0.75, 0.4, -0.7]))
    H.write(HERE/'cameras.json', H.camera_set(STANCE, DRAWN_DROP, head_dist=4.6, head_views=views)
            + H.grip_cameras(STANCE, DRAWN_DROP, WEAPONS))
    H.write_flex(HERE, 'beam', PARTS, WEAPONS, MATERIALS)
    H.write_emblem(HERE/'raiko_emblem.png', emblem_raiko())


if __name__ == '__main__':
    main()
