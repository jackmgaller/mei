#!/usr/bin/env python3
"""Writes sled.asset.json and its artwork (art/) beside this file.

The recipe is generated: change this script and run it (python3 make_sled.py), do not edit it.
The Synergen hover-sled, 2.4 m long, facing -Z (the game turns it to travel +z), its origin on
the snow under its middle; it hovers, the hull's belly 0.28 m up. Parts:

  hull      pearl-white deck, cyan shoulders, a chrome side band, graphite belly; the Synergen
            wordmark lit on the tail panel (emissive: unshaded)
  canopy    a closed bubble over the cockpit, material `glass` (tag glass), semi-transparent
            (`blend: "half"`, BLEND_HALF), so the pilot shows through
  pilot     helmet with a tangerine mirror visor, suit, arms
  pods      two chrome hover pods on swept struts, cyan thruster glows at the back (emissive)
  spoiler   a rear wing on two struts

Lighting is baked for the sled as drawn: turned 180 degrees, with the sun high, ahead and to the
left of the descent (world (-0.45, 0.8, 0.4); in the model's frame (0.45, 0.8, -0.4)).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True     # no __pycache__ beside the recipes
sys.path.insert(0, str(HERE))
from herokit import (Mesh, loft, box_mesh, write_recipe, text_image, chrome_strip, save,  # noqa: E402
                     WHITE, PEARL, CYAN, BLUE, LIME, TANGERINE, GRAPHITE, SILVER)

# Hull stations along z (nose -Z): z, half-width, deck height, belly height.
STATIONS = [(-1.25, 0.00, 0.40, 0.40), (-1.02, 0.20, 0.47, 0.34), (-0.70, 0.34, 0.54, 0.30),
            (-0.30, 0.43, 0.60, 0.28), (0.15, 0.47, 0.64, 0.28), (0.55, 0.46, 0.66, 0.29),
            (0.85, 0.44, 0.66, 0.30), (1.12, 0.40, 0.64, 0.33)]


def hull_section(w, t, b):
    """Ten points around the hull at one station, (x, y): the right side from the deck's centre
    stripe down to the belly, then the left side back up."""
    h = t-b
    right = [(0.2*w, t-0.004), (0.62*w, t-0.035), (w, b+0.55*h), (0.92*w, b+0.2*h), (0.5*w, b)]
    return right+[(-x, y) for x, y in reversed(right)]


def hull():
    m = Mesh()
    rings = []
    for z, w, t, b in STATIONS:
        if w == 0:
            rings.append([m.vert([0, t, z])])
            continue
        rings.append([m.vert([x, y, z]) for x, y in hull_section(w, t, b)])

    # Sides (from point j to j+1): 0 deck R, 1 shoulder R, 2 side R, 3 chine R, 4 belly,
    # 5 chine L, 6 side L, 7 shoulder L, 8 deck L, 9 the centre stripe.
    def mat(i, j):
        if j == 9:
            return 'blue'
        if j in (0, 8):
            return 'cyan' if i <= 1 else 'pearl'
        if j in (1, 7):
            return 'lime' if i == 5 else 'cyan'
        if j in (2, 6):
            return 'chrome'
        return 'graphite'

    def inside(p):
        return [0.0, 0.46, min(max(p[2], -1.0), 1.0)]

    loft(m, rings, mat, inside)
    # Chrome UVs: v by height across the side band (0 at its top edge, 1 at the bottom).
    for i, (z, w, t, b) in enumerate(STATIONS):
        if w == 0:
            continue
        h = t-b
        top, bot = b+0.55*h, b+0.2*h
        for k in rings[i]:
            y = m.v[k][1]
            m.uv[k] = [z*0.5, (top-y)/(top-bot)*0.9+0.05]
    # The tail panel (its own vertices, for the wordmark's UVs), facing +Z.
    z, w, t, b = STATIONS[-1]
    pts = hull_section(w, t, b)
    idx = [m.vert([x, y, z], [(w-x)/(2*w), 0.08+0.84*(t-y)/(t-b)]) for x, y in pts]
    m.poly(idx, 'logo', want=[0, 0, 1])
    return m


def canopy():
    """An ellipsoidal bubble: base ring sunk into the deck, 10 around, 3 latitudes and a top."""
    m = Mesh()
    cx, y0, cz, rx, ry, rz = 0.0, 0.50, -0.15, 0.34, 0.40, 0.62
    rings = []
    for phi in (0, 38, 68):
        p = math.radians(phi)
        rings.append([m.vert([cx+rx*math.cos(p)*math.sin(a), y0+ry*math.sin(p),
                              cz-rz*math.cos(p)*math.cos(a)])
                      for a in (2*math.pi*k/10 for k in range(10))])
    rings.append([m.vert([cx, y0+ry, cz])])
    loft(m, rings, lambda i, j: 'glass', lambda p: [cx, y0, cz])
    return m


def sphere(m, c, r, seg, lats, mat_fn):
    """A UV sphere: poles and `lats` latitudes (degrees, south to north, exclusive of the poles).
    mat_fn(normal) picks each face's material."""
    rings = [[m.vert([c[0], c[1]-r[1], c[2]])]]
    for lat in lats:
        p = math.radians(lat)
        rings.append([m.vert([c[0]+r[0]*math.cos(p)*math.sin(a), c[1]+r[1]*math.sin(p),
                              c[2]-r[2]*math.cos(p)*math.cos(a)])
                      for a in (2*math.pi*k/seg for k in range(seg))])
    rings.append([m.vert([c[0], c[1]+r[1], c[2]])])

    def mat(i, j):
        a0 = 2*math.pi*(j+0.5)/seg
        lat_lo = -90 if i == 0 else lats[i-1]
        lat_hi = 90 if i == len(lats) else lats[i]
        p = math.radians((lat_lo+lat_hi)/2)
        return mat_fn([math.cos(p)*math.sin(a0), math.sin(p), -math.cos(p)*math.cos(a0)])

    loft(m, rings, mat, lambda p: c)


def pilot():
    m = Mesh()
    # Helmet: white shell, a tangerine mirror visor across the front, a cyan crest stripe.
    def helmet(n):
        if n[2] < -0.55 and -0.45 < n[1] < 0.5:
            return 'visor'
        if abs(n[0]) < 0.3 and n[1] > 0.6:
            return 'cyan'
        return 'white'
    sphere(m, [0, 0.75, -0.08], [0.12, 0.115, 0.13], 8, (-35, 15, 55), helmet)
    # Torso: shoulders under the helmet, leaning forward, sunk into the deck.
    lo, hi = 0.52, 0.69
    corners = [(-0.20, hi, -0.02), (0.20, hi, -0.02), (0.20, hi, 0.14), (-0.20, hi, 0.14),
               (-0.16, lo, 0.04), (0.16, lo, 0.04), (0.16, lo, 0.30), (-0.16, lo, 0.30)]
    v = [m.vert(list(p)) for p in corners]
    cen = [0, 0.6, 0.12]
    for q, mat in (([0, 1, 2, 3], 'blue'), ([4, 5, 6, 7], 'blue'), ([0, 1, 5, 4], 'blue'),
                   ([3, 2, 6, 7], 'blue'), ([0, 3, 7, 4], 'white'), ([1, 2, 6, 5], 'white')):
        m.poly([v[k] for k in q], mat, inside=cen)
    # Arms: from the shoulders forward and down to the grips.
    for s in (-1, 1):
        a = [(s*0.15, 0.62, 0.02), (s*0.23, 0.62, 0.02), (s*0.23, 0.70, 0.02), (s*0.15, 0.70, 0.02),
             (s*0.12, 0.56, -0.40), (s*0.18, 0.56, -0.40), (s*0.18, 0.61, -0.40), (s*0.12, 0.61, -0.40)]
        v = [m.vert(list(p)) for p in a]
        cen = [s*0.17, 0.62, -0.19]
        for q in ([0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]):
            m.poly([v[k] for k in q], 'white', inside=cen)
    return m


def pod(s):
    """One hover pod at x = s * 0.64: an eight-sided chrome body (UVs: v by height), a nose cone,
    and at the back a lip around a recessed cyan thruster glow."""
    m = Mesh()
    xc, yc, seg = s*0.64, 0.38, 8
    stations = [(-0.80, 0.0), (-0.45, 0.15), (0.55, 0.17), (0.90, 0.145)]
    rmax = 0.17
    rings = []
    for z, r in stations:
        if r == 0:
            rings.append([m.vert([xc, yc, z], [z*0.5, 0.5])])
            continue
        ring = []
        for k in range(seg):
            a = 2*math.pi*(k+0.5)/seg
            x, y = xc+r*math.sin(a), yc+r*math.cos(a)
            ring.append(m.vert([x, y, z], [z*0.5, 0.5-(y-yc)/(2*rmax)*0.9]))
        rings.append(ring)
    inner = []
    for k in range(seg):
        a = 2*math.pi*(k+0.5)/seg
        inner.append(m.vert([xc+0.10*math.sin(a), yc+0.10*math.cos(a), 0.87]))
    rings.append(inner)
    def mat(i, j):
        return 'lip' if i == 3 else 'chrome'
    loft(m, rings, mat, lambda p: [xc, yc, min(max(p[2], -0.6), 0.75)], cap_end='thrust')
    return m


def struts():
    m = Mesh()
    for s in (-1, 1):
        # A swept plate from inside the hull to inside the pod.
        x0, x1 = s*0.36, s*0.60
        pts = [(x0, -0.15), (x1, 0.05), (x1, 0.45), (x0, 0.50)]
        ylo, yhi = 0.375, 0.415
        v = [m.vert([x, y, z]) for y in (ylo, yhi) for x, z in pts]
        cen = [(x0+x1)/2, (ylo+yhi)/2, 0.2]
        for q, mat in (([0, 1, 2, 3], 'blue'), ([4, 5, 6, 7], 'blue'), ([0, 1, 5, 4], 'blue'),
                       ([1, 2, 6, 5], 'blue'), ([2, 3, 7, 6], 'blue'), ([3, 0, 4, 7], 'blue')):
            m.poly([v[k] for k in q], mat, inside=cen)
    return m


def spoiler():
    m = Mesh()
    # The wing: a thin slab, its top carrying the wordmark (UVs read upright from behind).
    x0, x1, y0, y1, z0, z1 = -0.62, 0.62, 0.84, 0.88, 0.86, 1.08
    box_mesh(m, [x0, y0, z0], [x1, y1, z1], {'left': 'blue', 'right': 'blue', 'bottom': 'white',
                                             'top': 'cyan', 'back': 'blue', 'front': 'lime'})
    # Two struts from the deck to the wing.
    for s in (-1, 1):
        box_mesh(m, [s*0.30-0.025, 0.60, 0.90], [s*0.30+0.025, 0.85, 1.02], 'blue',
                 skip=('top', 'bottom'))
    return m


def artwork():
    art = HERE/'art'
    im = text_image('SYNERGEN', 64, 24, '#ffffff', BLUE, fill=0.92, box=(2, 2, 62, 17),
                    underline=(LIME, 2, 1))
    save(im, art/'sled_logo.png')
    chrome_strip(art/'chrome.png')


def recipe():
    parts = [('hull', hull()), ('canopy', canopy()), ('pilot', pilot()), ('pod_left', pod(-1)),
             ('pod_right', pod(1)), ('struts', struts()), ('spoiler', spoiler())]
    for name, m in parts:
        print(f'{name}: {m.tris()} triangles')
    print('total', sum(m.tris() for _, m in parts))
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'sled',
        'budget': {'vertices': 600, 'triangles': 500},
        'materials': {
            'pearl': {'color': PEARL, 'smooth': True},
            'white': {'color': WHITE},
            'cyan': {'color': CYAN, 'smooth': True},
            'lime': {'color': LIME},
            'blue': {'color': BLUE},
            'graphite': {'color': GRAPHITE},
            'visor': {'color': TANGERINE},
            'lip': {'color': SILVER},
            'glass': {'color': '#38b8e8', 'smooth': True, 'tag': 'glass', 'blend': 'half'},
            'thrust': {'color': '#40f0ff', 'class': 'emissive', 'tag': 'thrust'},
            'chrome': {'color': '#b8d8f0', 'class': 'emissive', 'tag': 'chrome',
                       'texture': {'image': 'art/chrome.png', 'projection': 'planar'}},
            'logo': {'color': BLUE, 'class': 'emissive', 'tag': 'logo',
                     'texture': {'image': 'art/sled_logo.png', 'projection': 'fit'}},
        },
        'lighting': {'direction': [0.45, 0.8, -0.4], 'ambient': 0.65},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': [m.node(name) for name, m in parts],
    }


if __name__ == '__main__':
    artwork()
    write_recipe(HERE/'sled.asset.json', recipe())
