#!/usr/bin/env python3
"""Writes park_swings.asset.json, park_swings_col.asset.json, park_swings.cameras.json and art/
beside this script (python3 make_park_swings.py; needs Pillow): the park's swings (shrine town
spec 3.16; assets.md #29), a 1990s two-seat swing set: a green steel A-frame (top bar at 2.5 m,
4.2 m long), two red seats on chains, and the low yellow safety rail in front.

Asset frame: origin at the centre of the whole footprint (frame and rail) at the ground; the
seats swing along Z, the rail is on the -Z side (the front). The frame's top bar is at
z = FRAME_Z, 0.6 m behind the origin; the grey box's swings block (z 140-141) was the frame.

What the player uses:
- The top bar, a rail to grind or hang from: x -2.1 -> 2.1 at y TOP (2.5), z FRAME_Z. Its
  collision top (0.2 wide, at 2.6) is standable.
- The safety rail, a rail to grind: x -2.2 -> 2.2 at y RAIL_Y (0.625), z RAIL_Z. Its collision is a
  0.2 m wall 0.65 high.
- The seats, standable at 0.45 (a hop); they do not move.
- The legs lean (no poles).
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arch_wall_gate'))
import arch_parts as ap  # noqa: E402

ART = HERE / 'art'

TOP = 2.5          # the top bar's centre
BAR = 0.07         # its section
BAR_X = 2.1
LEG_X = 2.0
LEG_Z = 0.8        # the legs' feet, +-, from the frame's plane
LEG = 0.06
BRACE_Y = 0.9
SEAT_X = 0.95      # seats at x +-SEAT_X
SEAT_W, SEAT_T, SEAT_D = 0.46, 0.05, 0.17
SEAT_Y = 0.42      # the seat's centre
CHAIN_W = 0.5      # the chains' plane: the chains 0.2 either side of the seat's centre
RAIL_X = 2.2
RAIL_Y = 0.6       # the safety rail's centre
RAIL_P = 0.05
RAIL_DZ = -2.0     # the rail, from the frame
# centre the footprint (rail front to the legs' back feet)
SHIFT = -((RAIL_DZ - 0.03) + (LEG_Z + LEG / 2)) / 2
FRAME_Z = SHIFT
RAIL_Z = RAIL_DZ + SHIFT

COL = {'green': '#40a060', 'red': '#d8462a', 'yellow': '#d8b048', 'chain': '#b4b8bc'}


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def draw_art():
    """The chains: 16 x 64 texels over the 0.5 x 2.05 m plane a seat hangs in, a chain one
    texel wide 0.2 m either side of the middle, links light and dark by turns, the hanger
    shackle at the top."""
    ART.mkdir(exist_ok=True)
    im = Image.new('RGBA', (16, 64), (0, 0, 0, 0))
    px = im.load()
    light, dark, shackle = rgb('#d0d4d8'), rgb('#7e8488'), rgb('#4a4e52')
    for c in (1, 14):
        for y in range(64):
            px[c, y] = shackle if y < 2 else (light if (y // 2) % 2 == 0 else dark)
    im.save(ART / 'chains.png')


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def mul(a, s):
    return tuple(c * s for c in a)


def prism(part, mat, a, b, r, sides=3, roll=0.0):
    """A pipe from a to b as an open prism (no ends) of `sides` faces, circumradius r."""
    d = ap.unit(ap.sub(b, a))
    ref = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (0.0, 0.0, 1.0)
    u = ap.unit(ap.cross(d, ref))
    v = ap.cross(u, d)
    ring = []
    for k in range(sides):
        t = roll + 2 * math.pi * k / sides
        ring.append(add(mul(u, r * math.cos(t)), mul(v, r * math.sin(t))))
    for k in range(sides):
        o0, o1 = ring[k], ring[(k + 1) % sides]
        pts = [add(a, o0), add(a, o1), add(b, o1), add(b, o0)]
        out = add(o0, o1)
        n = ap.cross(ap.sub(pts[1], pts[0]), ap.sub(pts[2], pts[0]))
        if ap.dot(n, out) < 0:
            pts.reverse()
        part.face(mat, pts)


def legs():
    """The four legs' (top, foot) points."""
    out = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            out.append(((sx * LEG_X, TOP, FRAME_Z), (sx * LEG_X, 0.0, FRAME_Z + sz * LEG_Z)))
    return out


def brace_z():
    return LEG_Z * (1 - BRACE_Y / TOP)


def level0():
    fr = ap.Part('frame')
    h = BAR / 2
    fr.box('green', -BAR_X, BAR_X, TOP - h, TOP + h, FRAME_Z - h, FRAME_Z + h)
    for top, foot in legs():
        prism(fr, 'green', top, foot, LEG / math.sqrt(3) * 1.15, roll=math.pi / 2)
    bz = brace_z()
    for sx in (-1, 1):
        prism(fr, 'green', (sx * LEG_X, BRACE_Y, FRAME_Z - bz), (sx * LEG_X, BRACE_Y, FRAME_Z + bz),
              0.03, roll=math.pi / 2)
    seats = ap.Part('seats')
    ch = ap.Part('chains')
    for sx in (-1, 1):
        x = sx * SEAT_X
        seats.box('red', x - SEAT_W / 2, x + SEAT_W / 2, SEAT_Y - SEAT_T / 2, SEAT_Y + SEAT_T / 2,
                  FRAME_Z - SEAT_D / 2, FRAME_Z + SEAT_D / 2, open=('bottom',))
        ch.face('chains', [(x - CHAIN_W / 2, TOP, FRAME_Z), (x + CHAIN_W / 2, TOP, FRAME_Z),
                           (x + CHAIN_W / 2, SEAT_Y, FRAME_Z), (x - CHAIN_W / 2, SEAT_Y, FRAME_Z)],
                [(0, 0), (1, 0), (1, 1), (0, 1)])
    rail = ap.Part('safety_rail')
    p = RAIL_P / 2
    q = 0.03
    for sx in (-1, 1):
        x = sx * RAIL_X
        rail.box('yellow', x - q, x + q, 0.0, RAIL_Y + p, RAIL_Z - q, RAIL_Z + q, open=('bottom',))
    # the bar between the posts, its open ends on the posts' faces
    rail.box('yellow', -RAIL_X + q, RAIL_X - q, RAIL_Y - p, RAIL_Y + p,
             RAIL_Z - p, RAIL_Z + p, open=('left', 'right'))
    return [fr, seats, ch, rail]


def level1():
    """From 25 m: the bar and legs as three-sided pipes, the seats' tops; no chains, no rail."""
    fr = ap.Part('frame')
    prism(fr, 'green', (-BAR_X, TOP, FRAME_Z), (BAR_X, TOP, FRAME_Z), BAR / math.sqrt(3) * 1.15,
          roll=math.pi / 2)
    for top, foot in legs():
        prism(fr, 'green', top, foot, LEG / math.sqrt(3) * 1.15, roll=math.pi / 2)
    for sx in (-1, 1):
        x = sx * SEAT_X
        y = SEAT_Y + SEAT_T / 2
        fr.face('red', [(x - SEAT_W / 2, y, FRAME_Z + SEAT_D / 2), (x + SEAT_W / 2, y, FRAME_Z + SEAT_D / 2),
                        (x + SEAT_W / 2, y, FRAME_Z - SEAT_D / 2), (x - SEAT_W / 2, y, FRAME_Z - SEAT_D / 2)])
    return [fr]


def collision():
    b = ap.Part('body')
    ap.col_box(b, -BAR_X - 0.05, BAR_X + 0.05, TOP - 0.1, TOP + 0.1, FRAME_Z - 0.1, FRAME_Z + 0.1)
    for top, foot in legs():
        # a leaning column 0.2 square, from the bar's underside to the ground
        tz, fz = top[2], foot[2]
        y0 = TOP - 0.1
        tz = fz + (tz - fz) * (y0 / TOP)
        x = top[0]
        w = 0.1 if fz < FRAME_Z else 0.09    # the two legs of an A meet at the top: not coplanar
        c = [((x - w, x + w), (z - 0.1, z + 0.1), y) for z, y in ((fz, 0.0), (tz, y0))]
        (xa, xb), (fa, fb), _ = c[0]
        _, (ta, tb), _ = c[1]
        ap.col_quad(b, (xa, y0, ta), (xb, y0, ta), (xb, 0.0, fa), (xa, 0.0, fa))     # -Z side
        ap.col_quad(b, (xb, y0, tb), (xa, y0, tb), (xa, 0.0, fb), (xb, 0.0, fb))     # +Z side
        ap.col_quad(b, (xb, y0, ta), (xb, y0, tb), (xb, 0.0, fb), (xb, 0.0, fa))     # +X side
        ap.col_quad(b, (xa, y0, tb), (xa, y0, ta), (xa, 0.0, fa), (xa, 0.0, fb))     # -X side
    bz = brace_z()
    for sx in (-1, 1):
        x = sx * LEG_X
        ap.col_box(b, x - 0.08, x + 0.08, BRACE_Y - 0.1, BRACE_Y + 0.1, FRAME_Z - bz, FRAME_Z + bz,
                   open=('back', 'front'))
        xs = sx * SEAT_X
        ap.col_box(b, xs - SEAT_W / 2, xs + SEAT_W / 2, SEAT_Y + SEAT_T / 2 - 0.2, SEAT_Y + SEAT_T / 2,
                   FRAME_Z - 0.1, FRAME_Z + 0.1)
    ap.col_box(b, -RAIL_X - 0.06, RAIL_X + 0.06, 0.0, RAIL_Y + 0.05, RAIL_Z - 0.1, RAIL_Z + 0.1,
               open=('bottom',))
    return [b]


MATS = {
    'green': {'color': COL['green'], 'palette': True},
    'red': {'color': COL['red'], 'palette': True},
    'yellow': {'color': COL['yellow'], 'palette': True},
    'chains': {'color': COL['chain'], 'double_sided': True,
               'texture': {'image': 'art/chains.png', 'projection': 'fit'}},
}


def cam(name, eye, target):
    return {'name': name, 'eye': [eye[0], eye[1], eye[2] + FRAME_Z],
            'target': [target[0], target[1], target[2] + FRAME_Z]}


CAMERAS = [
    cam('eye', (1.0, 1.6, -7.0), (0, 1.2, 0)),
    cam('end', (6.5, 1.6, -1.0), (0, 1.3, 0)),
    cam('seat', (-0.4, 1.6, -2.4), (-0.95, 0.8, 0)),
    cam('on_bar', (0.0, 4.2, -2.5), (0, 2.5, 0)),
    cam('above', (-6.0, 7.0, -6.0), (0, 1.0, 0)),
    cam('far', (10.0, 3.0, -28.0), (0, 1.2, 0)),
]


def main():
    draw_art()
    lod = {'levels': [(25, level1())], 'cull': 80, 'band': 2}
    ap.write(HERE / 'park_swings.asset.json', ap.recipe('park_swings', MATS, level0(), 100, lod))
    ap.write(HERE / 'park_swings_col.asset.json', ap.col_recipe('park_swings_col', collision()))
    (HERE / 'park_swings.cameras.json').write_text(json.dumps(CAMERAS, indent=1) + '\n')
    print('frame z', round(FRAME_Z, 3), 'rail z', round(RAIL_Z, 3))


if __name__ == '__main__':
    main()
