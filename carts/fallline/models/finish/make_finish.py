#!/usr/bin/env python3
"""Writes finish.asset.json and its artwork (art/) beside this file.

The recipe is generated: change this script and run it (python3 make_finish.py), do not edit it.
The finish arch facing -Z, origin on the snow under its middle, 8 m high:

  towers    two frosted-white towers, centres at x = +-12.6 (the clear span between them is
            about 24 m), 1 m into the snow, with light strips on their fronts (material `light`,
            emissive), lime and chrome collars and chrome spires
  arch      a chrome tube curving from tower to tower, its top 8 m above the snow, a light strip
            (emissive `light`) along its underside
  banner    FINISH between chequered borders, lit (emissive), hung from the arch on two hangers,
            its underside 3.4 m above the snow

Lighting is baked for yaw 0, the sun high, ahead and to the left of the descent:
(-0.45, 0.8, 0.4).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True     # no __pycache__ beside the recipes
sys.path.insert(0, str(HERE.parent/'sled'))
from herokit import (Mesh, loft, box_mesh, write_recipe, text_image, chrome_strip, save,  # noqa: E402
                     CYAN, BLUE, LIME)

TOWER_X = 12.6
TOP = 8.0                 # the arch's highest point
TUBE_R = 0.6
END_Y = 4.4               # the arch's centreline where it enters a tower
BANNER = (-4.6, 4.6, 3.4, 6.3)


def octagon(xc, y, hx, hz):
    c = math.cos(math.radians(22.5))
    return [[xc+hx*math.sin(math.radians(22.5+45*k))/c, y,
             -hz*math.cos(math.radians(22.5+45*k))/c] for k in range(8)]


def tower(s):
    m = Mesh()
    xc = s*TOWER_X
    stations = [(-1.0, 0.75, 0.6), (4.2, 0.68, 0.55), (4.45, 0.68, 0.55), (4.95, 0.68, 0.55),
                (5.05, 0.5, 0.42)]
    rings = []
    for y, hx, hz in stations:
        rings.append([m.vert(p, [p[0]*0.5, 0.05+0.9*(4.95-p[1])/0.5])
                      for p in octagon(xc, y, hx, hz)])
    rings.append([m.vert([xc, 5.9, 0.0])])
    inner = 5 if s > 0 else 1

    def mat(i, j):
        if i == 0:
            return 'light' if j in (7, inner) else 'frost'
        if i == 1:
            return 'lime'
        if i == 2:
            return 'chrome'
        return 'spire'
    loft(m, rings, mat, lambda p: [xc, min(max(p[1], -0.9), 5.0), 0.0])
    return m


def arch_y(x):
    return TOP-TUBE_R-(TOP-TUBE_R-END_Y)*(x/TOWER_X)**2


def arch():
    """An eight-sided tube along y = arch_y(x), x from one tower's centre to the other's; open
    at the ends, which are inside the towers. Chrome above (UVs: v by height across the tube), a
    light strip along the underside between two blue faces."""
    m = Mesh()
    n, sides = 16, 8
    rings = []
    for i in range(n+1):
        x = -TOWER_X+2*TOWER_X*i/n
        y = arch_y(x)
        dydx = -2*(TOP-TUBE_R-END_Y)*x/TOWER_X**2
        t = [1.0, dydx]
        L = math.hypot(*t)
        nx, ny = -t[1]/L, t[0]/L            # the normal in the XY plane, pointing up
        ring = []
        for k in range(sides):
            a = 2*math.pi*(k+0.5)/sides
            ca, sa = math.cos(a), math.sin(a)
            p = [x+TUBE_R*ca*nx, y+TUBE_R*ca*ny, TUBE_R*sa]
            ring.append(m.vert(p, [x*0.25, 0.5-0.45*ca]))
        rings.append(ring)

    def inside(p):
        return [p[0], arch_y(p[0]), 0.0]
    def mat(i, j):
        # Side j spans angles (j+0.5)..(j+1.5) * 45 degrees from the up direction (toward +Z
        # first): side 3 is the underside, 2 and 4 beside it.
        return 'light' if j == 3 else 'blue' if j in (2, 4) else 'chrome'
    loft(m, rings, mat, inside)
    return m


def banner():
    m = Mesh()
    x0, x1, y0, y1 = BANNER
    box_mesh(m, [x0, y0, -0.06], [x1, y1, 0.06],
             {'left': 'blue', 'right': 'blue', 'bottom': 'blue', 'top': 'blue',
              'back': 'board', 'front': 'board'})
    for f, mat in zip(m.f, m.fm):
        if mat != 'board':
            continue
        front = all(m.v[i][2] < 0 for i in f)
        for i in f:
            px, py, _ = m.v[i]
            u = (px-x0)/(x1-x0) if front else (x1-px)/(x1-x0)
            m.uv[i] = [u, (y1-py)/(y1-y0)]
    # Hangers from the banner's top into the arch.
    for s in (-1, 1):
        x = s*3.6
        box_mesh(m, [x-0.06, y1-0.05, -0.04], [x+0.06, arch_y(x)+0.1, 0.04], 'chrome_plain',
                 skip=('top', 'bottom'))
    return m


def artwork():
    from PIL import Image, ImageDraw
    art = HERE/'art'
    w, h = 64, 20
    im = text_image('FINISH', w, h, '#ffffff', BLUE, fill=0.95, box=(1, 4, 63, 16))
    d = ImageDraw.Draw(im)
    for y0 in (0, 16):
        for k in range(16):
            for r in range(2):
                col = '#ffffff' if (k+r) % 2 == 0 else '#101820'
                d.rectangle([k*4, y0+r*2, k*4+3, y0+r*2+1], fill=col)
    save(im, art/'finish_banner.png')
    chrome_strip(art/'chrome.png')


def recipe():
    parts = [('tower_left', tower(-1)), ('tower_right', tower(1)), ('arch', arch()),
             ('banner', banner())]
    for name, m in parts:
        print(f'{name}: {m.tris()} triangles')
    print('total', sum(m.tris() for _, m in parts))
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'finish',
        'budget': {'vertices': 400, 'triangles': 500},
        'materials': {
            'frost': {'color': '#e2f4fc', 'smooth': True},
            'lime': {'color': LIME},
            'blue': {'color': BLUE},
            'spire': {'color': CYAN},
            'chrome_plain': {'color': '#c4d4e4'},
            'light': {'color': '#20d8ff', 'class': 'emissive', 'tag': 'light'},
            'chrome': {'color': '#b8d8f0', 'class': 'emissive', 'tag': 'chrome',
                       'texture': {'image': 'art/chrome.png', 'projection': 'planar'}},
            'board': {'color': BLUE, 'class': 'emissive', 'tag': 'banner',
                      'texture': {'image': 'art/finish_banner.png', 'projection': 'fit'}},
        },
        'lighting': {'direction': [-0.45, 0.8, 0.4], 'ambient': 0.65},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': [m.node(name) for name, m in parts],
    }


if __name__ == '__main__':
    artwork()
    write_recipe(HERE/'finish.asset.json', recipe())
