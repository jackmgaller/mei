#!/usr/bin/env python3
"""Writes gate.asset.json and its artwork (art/) beside this file.

The recipe is generated: change this script and run it (python3 make_gate.py), do not edit it.
A Synergen gate pair facing -Z, origin on the snow midway between the posts:

  posts     two slim frosted-white obelisks, centres at x = +-3, 3.35 m tall and 1 m into the
            snow, each with a light strip on its front and inner faces (material `light`,
            emissive, so the game can flash it through its palette entry), a lime and a chrome
            collar and a cyan tip
  banner    the Synergen wordmark repeated across the gap, lit (emissive), its underside 2.56 m
            above the snow

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
                     WHITE, CYAN, BLUE, LIME)

POST_X = 3.0
BANNER = (2.56, 3.06)


def octagon(xc, y, hx, hz):
    """Eight points around (xc, y, 0): a stretched octagon, starting at the front (-Z) face's
    right corner and going round through +X."""
    pts = []
    for k in range(8):
        a = math.radians(22.5+45*k)
        pts.append([xc+hx*math.sin(a)/math.cos(math.radians(22.5)), y,
                    -hz*math.cos(a)/math.cos(math.radians(22.5))])
    return pts


def post(s):
    m = Mesh()
    xc = s*POST_X
    stations = [(-1.0, 0.21, 0.15), (2.30, 0.18, 0.13), (2.40, 0.18, 0.13), (2.66, 0.18, 0.13),
                (2.90, 0.12, 0.09)]
    rings = []
    for y, hx, hz in stations:
        pts = octagon(xc, y, hx, hz)
        rings.append([m.vert(p, [p[0]*2, 0.05+0.9*(2.66-p[1])/0.26]) for p in pts])
    rings.append([m.vert([xc, 3.35, 0.0])])
    # Side k runs from point k to k+1; side 7 is the front (-Z) face (points 7 and 0).
    # The inner face (toward x = 0) is side 5 for the right post (s = 1), side 1 for the left.
    inner = 5 if s > 0 else 1
    front_inner = 6 if s > 0 else 0

    def mat(i, j):
        if i == 0:
            return 'light' if j in (7, inner, front_inner) else 'frost'
        if i == 1:
            return 'lime'
        if i == 2:
            return 'chrome'
        return 'tip'
    loft(m, rings, mat, lambda p: [xc, min(max(p[1], -0.9), 3.0), 0.0])
    return m


def banner():
    m = Mesh()
    lo, hi = BANNER
    x = POST_X-0.06       # the ends sunk into the posts
    box_mesh(m, [-x, lo, -0.04], [x, hi, 0.04],
             {'left': 'frost', 'right': 'frost', 'bottom': 'blue', 'top': 'blue',
              'back': 'banner', 'front': 'banner'})
    # Wordmark UVs: three repeats across, upright from both sides.
    for f, mat in zip(m.f, m.fm):
        if mat != 'banner':
            continue
        front = all(m.v[i][2] < 0 for i in f)
        for i in f:
            px, py, _ = m.v[i]
            u = (px+3.0)/2.0 if front else (3.0-px)/2.0
            m.uv[i] = [u, (hi-py)/(hi-lo)]
    return m


def artwork():
    art = HERE/'art'
    im = text_image('SYNERGEN', 64, 16, '#ffffff', BLUE, fill=0.94, box=(3, 1, 61, 13),
                    underline=(LIME, 1, 0.5))
    save(im, art/'banner.png')
    chrome_strip(art/'chrome.png')


def recipe():
    parts = [('post_left', post(-1)), ('post_right', post(1)), ('banner', banner())]
    for name, m in parts:
        print(f'{name}: {m.tris()} triangles')
    print('total', sum(m.tris() for _, m in parts))
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'gate',
        'budget': {'vertices': 300, 'triangles': 200},
        'materials': {
            'frost': {'color': '#e2f4fc', 'smooth': True},
            'tip': {'color': CYAN},
            'lime': {'color': LIME},
            'blue': {'color': BLUE},
            'light': {'color': '#20d8ff', 'class': 'emissive', 'tag': 'light'},
            'chrome': {'color': '#b8d8f0', 'class': 'emissive', 'tag': 'chrome',
                       'texture': {'image': 'art/chrome.png', 'projection': 'planar'}},
            'banner': {'color': BLUE, 'class': 'emissive', 'tag': 'banner',
                       'texture': {'image': 'art/banner.png', 'projection': 'planar'}},
        },
        'lighting': {'direction': [-0.45, 0.8, 0.4], 'ambient': 0.65},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'nodes': [m.node(name) for name, m in parts],
    }


if __name__ == '__main__':
    artwork()
    write_recipe(HERE/'gate.asset.json', recipe())
