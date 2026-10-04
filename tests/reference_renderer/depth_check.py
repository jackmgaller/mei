#!/usr/bin/env python3
"""Scenes in the depth and perspective mode (docs/RENDERING.md), against depth.py.

Twelve views, each authored here as faces in world space under a camera: interpenetrating
boxes and faces, objects on a large platform (nearest first, farthest first, and with a far
limit), coplanar decals with and without an offset, drawn before and after their wall,
translucent panes over opaque faces, a grazing textured corridor (with the test on, and off with
perspective only), near-plane clipping with depth, the plane chip with polygons in both layers,
and an overload whose cost depends on the order alone. This script does the geometry itself (view
transform, near-plane clipping, projection, the view depth word, culling, order) and writes
the packets; the cost and pixels come from depth.py.

Each view is compared twice:

1. GPU only: depth_probe.c makes the view's register writes through Mei's bus. Framebuffer,
   depth buffer, displayed picture and the eight cycle and statistics counters must agree.
2. End to end: a cart (`depth.mei`) holds every view's register writes and packet lists,
   relocates the lists into RAM at start-up and plays the views one a frame in mei-headless.
   Each presented picture and its --gpu-stats row (cycles, counters) must agree with a
   reference that keeps one GPU's state across the frames, and the frame must take the ticks
   the 2,000,000-cycle budget gives it.

With --motion N, N more frames of a camera moving along the platform go into the cart (end to
end only), every fourth without GPU_ZCLEAR, so the depth buffer carries over from the frame
before.
"""
import argparse
import copy
import csv
import json
import math
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import common
import depth
import oracle

CART = common.cart_dir('depth')
NEAR = 0.5
BACKGROUND = 0x2108          # RGB555 (8, 8, 8)
SLOT_CHECKER, SLOT_BRICK, SLOT_POSTER = 4, 2, 6   # 4-bit, 8-bit (slots 2-3), 4-bit
ATLAS, MAP0, MAP1 = 0x60000, 0x50000, 0x50800     # plane chip data (VRAM offsets)
PLN = 0x700
LIGHT = (0.4, 0.8, -0.45)


# ---- VRAM: palettes, textures and the plane chip's atlas and maps

def c15(r, g, b):
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def vram_image():
    v = bytearray(1 << 20)
    palette = [0] * 4096
    for i in range(16):
        palette[16 + i] = c15(60 + i * 12, 70 + i * 10, 90 + i * 8)             # pal 1: checker
        palette[32 + i] = c15(250 - i * 14, 40 + i * 12, 30 + (i * 37) % 200)  # pal 2: poster
        palette[48 + i] = c15(40 + i * 6, 70 + i * 9, 140 + i * 7)             # pal 3: plane BG0
        palette[64 + i] = c15(20 + i * 4, 90 + i * 6, 110 + i * 8)             # pal 4: plane BG1
    palette[17] = c15(20, 22, 30)                                               # checker lines
    for i in range(256):
        light = 70 + (i * 29) % 160
        palette[512 + i] = c15(min(255, light + 40), light, max(0, light - 50))  # bank 2: brick
    v[depth.PALETTE:depth.PALETTE + 8192] = struct.pack('<4096H', *palette)
    checker = bytearray(32768)
    poster = bytearray(32768)
    for y in range(256):
        for x in range(256):
            a = 1 if x % 16 == 0 or y % 16 == 0 else 2 + ((x // 16 + y // 16) % 2) * 6 + (x * 3 + y) // 64 % 4
            r = math.hypot(x - 127.5, y - 127.5)
            b = 0 if r > 120 else 1 + int(r) // 9 % 15
            checker[y * 128 + x // 2] |= a << (4 * (x % 2))
            poster[y * 128 + x // 2] |= b << (4 * (x % 2))
    brick = bytearray(65536)
    for y in range(256):
        for x in range(256):
            row = y // 16
            mortar = y % 16 == 0 or (x + (16 if row % 2 else 0)) % 32 == 0
            hole = y >= 160 and (x // 12 + y // 12) % 2 == 0           # a fence: texel 0
            brick[y * 256 + x] = 0 if hole else 5 if mortar else 40 + (x // 32 * 37 + row * 23) % 200
    for slot, data in ((SLOT_CHECKER, checker), (SLOT_POSTER, poster), (SLOT_BRICK, brick)):
        start = depth.TEXTURE + slot * 32768
        v[start:start + len(data)] = data
    atlas = bytearray(4 * 1024)               # tiles 0-3 of a 4-bit, 8x8 atlas (row 0)
    for tile in range(4):
        for y in range(8):
            for x in range(8):
                i = 0 if tile == 0 else 1 + (x + y) % 3 if tile == 1 else 6 + (y // 2) if tile == 2 else 12 + x % 4
                atlas[y * 128 + (tile * 8 + x) // 2] |= i << (4 * (x % 2))
    v[ATLAS:ATLAS + len(atlas)] = atlas
    m0 = [1 + (x // 4 + y // 3) % 2 * 2 for y in range(32) for x in range(32)]       # the sky
    m1 = [(3 if y >= 21 and (x + y) % 7 else 0) | (0x4000 if x % 2 else 0) for y in range(32) for x in range(32)]
    v[MAP0:MAP0 + 2048] = struct.pack('<1024H', *m0)
    v[MAP1:MAP1 + 2048] = struct.pack('<1024H', *m1)
    return v


VRAM_RECORDS = [(depth.PALETTE, 8192), (depth.TEXTURE + SLOT_CHECKER * 32768, 32768),
                (depth.TEXTURE + SLOT_POSTER * 32768, 32768), (depth.TEXTURE + SLOT_BRICK * 32768, 65536),
                (ATLAS, 4096), (MAP0, 4096)]


def plane_registers():
    r = [0] * 64
    r[0] = 1                                        # the compositor on, no auto-erase, no dither
    r[1] = 3                                        # BG0 and BG1
    r[2] = 1 | 3 << 8 | 2 << 24 | 4 << 28           # BG0 1, BG1 3; PL 2, PH 4
    r[3] = 4 << 4                                   # BG1 averages with what is behind it
    r[5] = 0x302018
    r[8:12] = [3 << 8, ATLAS, MAP0, 13]             # BG0: 32x32 map, 8x8 4-bit, palette page 3
    r[16:20] = [4 << 8, ATLAS, MAP1, 5 << 16]       # BG1: palette page 4, scrolled down 5
    return r


# ---- geometry: faces in world space, a camera, near clipping, projection

def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a):
    n = math.sqrt(dot(a, a))
    return [x / n for x in a]


def face(points, colour, uv=None, tex=None, semi=None, decal=0, double=False, upper=False,
         normal=None, shade=True):
    """points in strip order (a quad is 0-1-2 and 1-2-3); tex = (slot, four, pal, window)."""
    n = normal or unit(cross(sub(points[1], points[0]), sub(points[2], points[0])))
    k = 0.55 + 0.45 * abs(dot(n, unit(LIGHT))) if shade else 1
    cols = [[min(255, int(c * k)) for c in (colour if isinstance(colour[0], int) else colour[i])]
            for i in range(len(points))]
    return {'points': points, 'cols': cols, 'uv': uv, 'tex': tex, 'semi': semi, 'decal': decal,
            'double': double, 'upper': upper, 'normal': n}


def quad(o, du, dv, colour, uv=((0, 0), (255, 0), (0, 255), (255, 255)), **kw):
    """The parallelogram o, o + du, o + dv, o + du + dv."""
    points = [o, [a + b for a, b in zip(o, du)], [a + b for a, b in zip(o, dv)],
              [a + b + c for a, b, c in zip(o, du, dv)]]
    return face(points, colour, [list(t) for t in uv] if kw.get('tex') else None, **kw)


def box(centre, size, colour, yaw=0.0, tex=None, upper=False):
    """Six outward faces of a box turned by yaw about the vertical."""
    c, s = math.cos(yaw), math.sin(yaw)
    axes = [[c * size[0] / 2, 0, -s * size[0] / 2], [0, size[1] / 2, 0], [s * size[2] / 2, 0, c * size[2] / 2]]
    faces = []
    for k in range(3):
        for sign in (-1, 1):
            i, j = [(1, 2), (2, 0), (0, 1)][k]
            if sign < 0:
                i, j = j, i
            centre_f = [centre[t] + sign * axes[k][t] for t in range(3)]
            o = [centre_f[t] - axes[i][t] - axes[j][t] for t in range(3)]
            du = [2 * axes[i][t] for t in range(3)]
            dv = [2 * axes[j][t] for t in range(3)]
            col = [min(255, x + 18 * k) for x in colour]
            faces.append(quad(o, du, dv, col, tex=tex, upper=upper, normal=unit([sign * a for a in axes[k]])))
    return faces


class Camera:
    def __init__(self, position, yaw, pitch):
        self.c = position
        self.f = [math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch)]
        self.r = unit(cross([0, 1, 0], self.f))
        self.u = cross(self.f, self.r)

    def view(self, p):
        d = sub(p, self.c)
        return [dot(d, self.r), dot(d, self.u), dot(d, self.f)]


def clip_near(vertices):
    """Sutherland-Hodgman against view depth NEAR; each vertex is [x, y, z, r, g, b, u, v]."""
    out = []
    for i, b in enumerate(vertices):
        a = vertices[i - 1]
        if (a[2] >= NEAR) != (b[2] >= NEAR):
            t = (NEAR - a[2]) / (b[2] - a[2])
            p = [x + (y - x) * t for x, y in zip(a, b)]
            p[2] = NEAR
            out.append(p)
        if b[2] >= NEAR:
            out.append(b)
    return out


def project(vertex):
    x, y, z = vertex[:3]
    sx, sy = math.floor(160 + 160 * x / z + 0.5), math.floor(120 - 160 * y / z + 0.5)
    if not (-32768 <= sx <= 32767 and -32768 <= sy <= 32767):
        raise ValueError('a vertex projects outside the 16-bit range: move the scene')
    return [sx, sy], round(z * 65536)


def packets_for(camera, faces):
    """(packet, mean view depth) for each visible face: near-clipped, projected, with depth."""
    out = []
    for f in faces:
        view = [camera.view(p) for p in f['points']]
        if not f['double'] and dot(f['normal'], sub(camera.c, f['points'][0])) <= 0:
            continue                                     # back-facing
        n = len(view)
        attrs = [view[i] + f['cols'][i] + (f['uv'][i] if f['uv'] else [0, 0]) for i in range(n)]
        polygon = [attrs[i] for i in ([0, 1, 3, 2] if n == 4 else [0, 1, 2])]
        clipped = clip_near(polygon)
        if len(clipped) < 3:
            continue
        unclipped = clipped == polygon
        pieces = [[attrs[i] for i in range(n)]] if unclipped else \
            [[clipped[0], clipped[i], clipped[i + 1]] for i in range(1, len(clipped) - 1)]
        for corners in pieces:
            projected = [project(c) for c in corners]
            tex = f['tex']
            p = {'flags': (2 if tex else 0) | (4 if len(corners) == 4 else 0) | (8 if f['semi'] is not None else 0),
                 'depth': True, 'blend': f['semi'] or 0, 'decal': f['decal'], 'upper': f['upper'],
                 'pos': [q[0] for q in projected], 'w': [q[1] for q in projected],
                 'cols': [[max(0, min(255, round(x))) for x in c[3:6]] for c in corners],
                 'uv': [[max(0, min(255, round(x))) for x in c[6:8]] for c in corners],
                 'slot': tex[0] if tex else 0, 'four': tex[1] if tex else False,
                 'pal': tex[2] if tex else 0, 'window': tex[3] if tex else 0}
            if len({tuple(c) for c in p['cols']}) > 1:
                p['flags'] |= 1
            out.append((p, sum(c[2] for c in corners) / len(corners)))
    return out


def ordered(camera, faces, order):
    """Packets in an order: 'near' (nearest first), 'far' (back to front), 'as_is'."""
    items = packets_for(camera, faces)
    if order != 'as_is':
        items.sort(key=lambda t: t[1], reverse=order == 'far')
    return [p for p, _ in items]


def overlay():
    """The interface, drawn after the scene with the test off: plain packets (no depth)."""
    bar = {'flags': 8, 'depth': False, 'blend': 0, 'pos': [[8, 216], [312, 216], [8, 232], [312, 232]],
           'cols': [[20, 40, 90]] * 4, 'uv': [[0, 0]] * 4, 'slot': 0, 'four': False, 'pal': 0, 'window': 0}
    bar['flags'] |= 4
    pip = dict(bar, flags=1, pos=[[14, 220], [40, 220], [14, 229]], cols=[[255, 220, 60], [255, 120, 40], [200, 255, 90]])
    return [bar, pip]


# ---- the views

CHECKER = (SLOT_CHECKER, True, 1, 0)
BRICK = (SLOT_BRICK, False, 2, 0)
POSTER = (SLOT_POSTER, True, 2, 0)


def floor(y, x0, x1, z0, z1, colour=(150, 150, 150), tex=CHECKER, repeat=1, upper=False):
    u = 255 * repeat if repeat == 1 else 255
    return quad([x0, y, z0], [x1 - x0, 0, 0], [0, 0, z1 - z0], colour, tex=tex, upper=upper,
                uv=((0, 0), (u, 0), (0, 255), (u, 255)), normal=[0, 1, 0])


def tiled_floor(y, x0, x1, z0, z1, n, m, colour=(150, 150, 150), tex=CHECKER):
    dx, dz = (x1 - x0) / n, (z1 - z0) / m
    return [quad([x0 + i * dx, y, z0 + j * dz], [dx, 0, 0], [0, 0, dz], colour, tex=tex, normal=[0, 1, 0])
            for j in range(m) for i in range(n)]


def interpenetrate():
    faces = tiled_floor(0, -8, 8, -2, 14, 4, 4, (120, 130, 110))
    faces += box([-0.6, 0.9, 4], [2, 1.8, 2], (200, 90, 70), yaw=0.5, tex=BRICK)
    faces += box([0.5, 1.1, 4.3], [1.6, 2.2, 1.6], (80, 160, 220), yaw=-0.35)
    # A large triangle through both boxes and the floor, and two crossed quads.
    faces.append(face([[-3, -0.5, 2.5], [3.2, 2.6, 6.5], [2.0, -0.6, 3.0]], [(255, 220, 90), (90, 255, 200), (230, 90, 255)],
                      double=True, normal=[0, 0, -1]))
    faces.append(quad([2.4, 0, 6], [2, 2.2, 0.4], [0, 0, 2.6], (230, 230, 120), tex=POSTER, double=True))
    faces.append(quad([3.6, 0, 6.2], [-1.2, 2.2, 1.2], [0.8, 0, 2.0], (120, 230, 230), tex=CHECKER, double=True))
    return Camera([0.4, 2.2, -1.5], 0.08, 0.28), [('opaque', faces, 'near')]


def platform(order='near'):
    faces = [floor(0, -40, 40, 0, 80, (110, 140, 100), repeat=1)]       # one huge face
    faces += box([0, 0.5, 18], [16, 1, 24], (150, 120, 90), tex=BRICK)  # a platform on it
    for i in range(6):
        faces += box([-5 + 2 * i, 1.6, 10 + 3.5 * i], [1.2, 1.2, 1.2], (90 + 25 * i, 200 - 20 * i, 120), yaw=0.3 * i)
    faces += box([4, 4, 28], [1, 8, 1], (220, 220, 230))                 # a pillar
    faces += box([-14, 1.5, 40], [6, 3, 6], (90, 100, 200), tex=CHECKER)
    return Camera([1, 2.6, 1.5], 0.05, 0.12), [('opaque', faces, order)]


def decals():
    wall = quad([-4, 0, 6], [8, 0, 0], [0, 4, 0], (170, 160, 150), tex=BRICK, normal=[0, 0, -1])
    floor_ = floor(0, -6, 6, 0.6, 30, (120, 120, 130))

    def on_wall(x, y, size, offset):
        return quad([x, y, 6], [size, 0, 0], [0, size, 0], (255, 255, 255), tex=POSTER, decal=offset,
                    normal=[0, 0, -1])

    def on_floor(x, z, length, offset):
        return quad([x, 0, z], [0.5, 0, 0], [0, 0, length], (250, 240, 90), decal=offset, normal=[0, 1, 0])

    before = [on_wall(-3.6, 2.2, 1.5, 0), on_wall(-1.6, 2.2, 1.5, 2), on_floor(-2.5, 1.5, 10, 2), on_floor(1.0, 1.5, 10, 8)]
    after = [on_wall(0.4, 2.2, 1.5, 0), on_wall(2.2, 2.2, 1.5, 2), on_floor(-0.75, 1.5, 10, 0)]
    return Camera([0, 1.2, -0.4], 0.0, 0.05), [('decals drawn first', before, 'as_is'),
                                               ('wall and floor', [wall, floor_], 'near'),
                                               ('decals drawn after', after, 'as_is')]


def glass():
    faces = tiled_floor(0, -6, 6, 0, 16, 3, 4, (110, 120, 140))
    faces += box([-1.5, 1, 6], [2, 2, 2], (210, 120, 60), yaw=0.4, tex=BRICK)
    faces += box([1.8, 0.75, 8], [1.5, 1.5, 1.5], (90, 200, 120), yaw=-0.2)
    panes = [quad([-3, 0.2, 4], [6, 0, 0.6], [0, 2.8, 0], (40, 120, 255), semi=0, double=True),
             quad([-0.5, 0.1, 5.2], [2.5, 0, 2.0], [0, 2.4, 0], (255, 90, 40), semi=1, double=True),
             quad([-2.5, 0.5, 7.5], [5, 0, 0], [0, 1.5, 0], (120, 120, 120), semi=3, tex=CHECKER, double=True)]
    late = box([3.2, 0.5, 9.5], [1, 1, 1], (230, 230, 80))                # drawn after the glass
    return Camera([0, 2.0, -1.0], 0.0, 0.2), [('opaque', faces, 'near'), ('glass, back to front', panes, 'far'),
                                              ('opaque after the glass', late, 'near')]


def corridor(test=True):
    faces = []
    for i in range(6):
        z0, z1 = 0.6 + i * 10, 0.6 + (i + 1) * 10
        faces.append(floor(0, -2, 2, z0, z1, (170, 170, 170)))
        faces.append(quad([-2, 0, z0], [0, 0, z1 - z0], [0, 3, 0], (160, 150, 140), tex=BRICK, normal=[1, 0, 0]))
        faces.append(quad([2, 0, z1], [0, 0, z0 - z1], [0, 3, 0], (150, 160, 170), tex=CHECKER, normal=[-1, 0, 0]))
    faces += box([0.8, 0.4, 14], [0.8, 0.8, 0.8], (200, 80, 80), tex=CHECKER)
    return Camera([-0.6, 0.45, -0.2], 0.1, 0.02), [('corridor', faces, 'near' if test else 'far')]


def near():
    faces = [floor(0, -3, 3, -2, 8, (160, 160, 150))]
    faces.append(quad([-0.9, 0, 0.0], [0, 0, 6], [0, 2.5, 0], (170, 150, 130), tex=BRICK, normal=[1, 0, 0]))
    faces += box([0.6, 0.6, 0.4], [1.0, 1.2, 1.4], (90, 170, 230), yaw=0.6, tex=CHECKER)   # through the near plane
    faces.append(face([[-1.5, 0.2, -1.0], [1.5, 1.9, 0.9], [0.4, 0.1, 3.0]], [(255, 100, 100), (100, 255, 100), (100, 100, 255)],
                      double=True))
    return Camera([0.0, 1.0, -0.2], 0.0, 0.25), [('opaque', faces, 'near')]


def planes():
    lower = box([-1.2, 1.0, 5], [1.8, 1.8, 1.8], (220, 120, 90), yaw=0.5, tex=BRICK)
    lower.append(floor(0, -4, 4, 2, 12, (120, 150, 120)))
    upper = box([0.6, 1.2, 5.2], [1.4, 2.2, 1.4], (110, 200, 240), yaw=-0.4, upper=True)  # intersects the lower box
    panes = [quad([-3, 2.4, 7], [6, 0, 0], [0, 1.6, 0], (255, 200, 60), semi=0, double=True),            # over holes
             quad([-2.5, 0.3, 4], [2.4, 0, 0], [0, 1.4, 0], (200, 80, 255), semi=1, double=True, upper=True)]
    return Camera([0, 2.2, -1.0], 0.0, 0.18), [('both layers', lower + upper, 'near'), ('panes', panes, 'far')]


def overload(order):
    faces = [quad([-6, -4.5, 3 + 0.25 * i], [12, 0, 0], [0, 9, 0], (100 + 10 * i, 120, 200 - 9 * i), tex=BRICK,
                  normal=[0, 0, -1], shade=False) for i in range(14)]
    return Camera([0, 0, 0], 0.0, 0.0), [('layers', faces, order)]


VIEWS = [
    ('interpenetrate', interpenetrate, {}),
    ('platform', lambda: platform('near'), {}),
    ('platform_far_first', lambda: platform('far'), {}),
    ('platform_far_limit', lambda: platform('near'), {'zclear': 0x7400}),   # nothing past 25.6 units
    ('decals', decals, {}),
    ('glass', glass, {}),
    ('corridor', corridor, {}),
    ('corridor_test_off', lambda: corridor(False), {'test': False}),
    ('near_clip', near, {}),
    ('planes', planes, {'planes': True}),
    ('overload_near_first', lambda: overload('near'), {}),
    ('overload_far_first', lambda: overload('far'), {}),
]


def writes_for(camera, batches, options):
    """A frame's register writes: the clear, the depth clear, the scene tested, the overlay not."""
    regs = plane_registers() if options.get('planes') else [0] * 64
    out = [(PLN + 4 * i, regs[i]) for i in (1, 2, 3, 5, 8, 9, 10, 11, 16, 17, 18, 19)] + [(PLN, regs[0])]
    out += [(depth.GPU_CTRL, 0 if options.get('planes') else 1),
            (depth.GPU_CLEAR, 0x8000 if options.get('planes') else BACKGROUND)]
    if options.get('zclear', 0) is not None:
        out.append((depth.GPU_ZCLEAR, options.get('zclear', 0)))
    out.append((depth.GPU_DEPTH, int(options.get('test', True))))
    for _, faces, order in batches:
        out.append((depth.GPU_DRAW, ordered(camera, faces, order)))
    out += [(depth.GPU_DEPTH, 0), (depth.GPU_DRAW, overlay())]
    return regs, out


class Frame:
    """A model GPU whose state (depth buffer, GPU_DEPTH, GPU_CTRL, the planes) lasts across
    frames, as the cart's does; returns each frame's display and statistics."""

    def __init__(self, vram):
        self.gpu = depth.Gpu(vram)

    def run(self, writes):
        g = self.gpu
        g.stats = dict.fromkeys(depth.STAT_NAMES, 0)
        for offset, value in writes:
            g.write(offset, value)
        return g.display(), dict(g.stats)


# ---- the cart

def script(vram, frames):
    """The cart's data: VRAM records, the packet lists with list-relative next fields, and each
    frame's writes ((offset, value) pairs; offset 0xFFFF draws list number value)."""
    words = [len(frames), len(VRAM_RECORDS)]
    for start, size in VRAM_RECORDS:
        words += [start, size // 4, *struct.unpack(f'<{size // 4}I', bytes(vram[start:start + size]))]
    lists, views = [], []
    for writes in frames:
        ops = []
        for offset, value in writes:
            if offset == depth.GPU_DRAW:
                body = []
                for i, p in enumerate(value):
                    rest = depth.words(p)
                    nxt = len(body) + len(rest) + 1 if i + 1 < len(value) else 0xFFFFFF
                    body += [((0x20 | (p['flags'] & 15) | (16 if p.get('depth') else 0)) << 24) | nxt, *rest]
                ops.append((0xFFFF, len(lists)))
                lists.append(body)
            else:
                ops.append((offset, value & 0xFFFFFFFF))
        views.append(ops)
    words.append(len(lists))
    for body in lists:
        words += [len(body), *body]
    for ops in views:
        words.append(len(ops))
        for o in ops:
            words += o
    return words, sum(len(b) for b in lists), len(lists)


CART_SOURCE = '''// Generated by tests/reference_renderer/depth_check.py: views in the depth mode, one a frame.
// Plays register writes and packet lists from depth.bin (docs/RENDERING.md); A pauses.
cart "Reference Renderer: depth"
embed SCRIPT: u32 = "depth.bin"
var lists: [{list_words}]u32
var starts: [{list_count}]u32
var views: [{view_count}]*u32
var shown: s32
var paused: bool

fn init() {{
    var p = SCRIPT
    let nviews = p[0] as s32
    let records = p[1] as s32
    p = p + 2
    for r in 0..records {{
        let dst = (0x400000 + p[0]) as *u32
        let n = p[1] as s32
        for k in 0..n {{ dst[k] = p[2 + k] }}
        p = p + 2 + n
    }}
    let nlists = p[0] as s32
    p = p + 1
    var used: s32 = 0
    for l in 0..nlists {{
        let n = p[0] as s32
        let base = &lists[used]
        starts[l] = base as u32
        var header: s32 = 0
        for k in 0..n {{
            var w = p[1 + k]
            if k == header {{
                let next = w & 0xFFFFFF
                if next != 0xFFFFFF {{
                    w = (w & 0xFF000000) | ((base as u32) + next * 4)
                    header = next as s32
                }}
            }}
            base[k] = w
        }}
        used += n
        p = p + 1 + n
    }}
    for v in 0..nviews {{
        views[v] = p
        p = p + 1 + 2 * (p[0] as s32)
    }}
}}

fn update() {{
    if btnp(A) {{ paused = !paused }}
}}

fn draw() {{
    let p = views[shown % {view_count}]
    let n = p[0] as s32
    for k in 0..n {{
        let offset = p[1 + 2 * k]
        let value = p[2 + 2 * k]
        if offset == 0xFFFF {{ GPU_DRAW = starts[value as s32] }}
        else {{ ((0xFF0000 + offset) as *u32)[0] = value }}
    }}
    if !paused {{ shown += 1 }}
}}
'''


def run_cart(frames, vram, out):
    words, list_words, list_count = script(vram, frames)
    (CART / 'depth.bin').write_bytes(struct.pack(f'<{len(words)}I', *words))
    (CART / 'depth.akr').write_text(CART_SOURCE.format(list_words=max(1, list_words), list_count=max(1, list_count),
                                                       view_count=len(frames)))
    rom = common.compile_cart('depth')
    ticks = 8 + 4 * len(frames)
    stats = out / 'cart_stats.csv'
    prefix = out / 'cart'
    subprocess.run([str(common.HEADLESS), str(rom), '--frames', str(ticks), '--dump-every', '1', str(prefix),
                    '--gpu-stats', str(stats), '--quiet'], check=True)
    rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stats.open())]
    return rows[:len(frames)], prefix


# ---- comparing and reporting

def rgb(fb):
    return np.array(oracle.rgb_image(fb & 0x7FFF))


def sheet(path, title, pictures):
    out = Image.new('RGB', (320 * len(pictures), 270), (15, 19, 28))
    pen = ImageDraw.Draw(out)
    for i, (label, picture) in enumerate(pictures):
        pen.text((i * 320 + 8, 8), f'{title}: {label}', fill='white')
        out.paste(Image.fromarray(picture), (i * 320, 30))
    out.resize((out.width * 2, 540), Image.Resampling.NEAREST).save(path)


def diff_image(a, b):
    d = np.zeros((240, 320, 3), dtype=np.uint8)
    d[np.any(a != b, axis=2) if a.ndim == 3 else a != b] = [255, 40, 90]
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--view', action='append', help='View name (repeatable); default all')
    parser.add_argument('--motion', type=int, default=0, help='Frames of camera motion in the cart')
    parser.add_argument('--no-cart', action='store_true', help='GPU-only comparisons alone')
    parser.add_argument('--out', type=Path, default=common.OUT / 'depth')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    probe = common.probe('depth_probe').resolve()
    vram = vram_image()
    views = [v for v in VIEWS if not args.view or v[0] in args.view]
    if not views:
        parser.error('no matching views')
    results, frames, names = [], [], []
    for name, build, options in views:
        camera, batches = build()
        regs, writes = writes_for(camera, batches, options)
        fb, zb, shown, stats = depth.model(vram, regs, writes)
        fb2, zb2, shown2, stats2 = depth.replay(probe, args.out / f'{name}.bin', vram, regs, writes)
        result = {'view': name, 'packets': sum(len(v) for o, v in writes if o == depth.GPU_DRAW),
                  'stats': stats,
                  'gpu_only': {'framebuffer': int((fb != fb2).sum()), 'depth_buffer': int((zb != zb2).sum()),
                               'display': int((shown != shown2).sum()),
                               'stats': {k: [stats[k], stats2[k]] for k in stats if stats[k] != stats2[k]}}}
        expected = rgb(shown)
        Image.fromarray(expected).save(args.out / f'{name}_reference.png')
        Image.fromarray(rgb(shown2)).save(args.out / f'{name}_gpu.png')
        keys = (zb >> 8).astype(np.uint8)
        Image.fromarray(keys).save(args.out / f'{name}_depth.png')
        results.append(result)
        frames.append(writes)
        names.append(name)
    order = {r['view']: r['stats']['gpu_cycles'] for r in results}
    checks, info = {}, {}
    checks['golden_values'] = not depth.golden()
    if 'platform' in order and 'platform_far_first' in order:
        checks['platform_near_first_cheaper'] = order['platform'] < order['platform_far_first']
    if 'overload_near_first' in order and 'overload_far_first' in order:
        checks['overload_near_first_in_budget'] = order['overload_near_first'] <= 2000000 < order['overload_far_first']
    # The same picture whichever order opaque faces come in, but for ties: none in the overload's
    # parallel layers; in the platform, where faces touch or cross and their keys are equal.
    pictures = {n: np.array(Image.open(args.out / f'{n}_reference.png')) for n in order}
    if 'overload_near_first' in order and 'overload_far_first' in order:
        checks['overload_same_picture_either_order'] = bool(np.array_equal(
            pictures['overload_near_first'], pictures['overload_far_first']))
    if 'platform' in order and 'platform_far_first' in order:
        info['platform_order_tie_pixels'] = int(np.any(pictures['platform'] != pictures['platform_far_first'], axis=2).sum())
    if args.motion:
        for i in range(args.motion):
            t = i / max(1, args.motion)
            camera = Camera([1 - 3 * t, 2.6 - 1.2 * t, 1.5 + 14 * t], 0.05 + 0.6 * t, 0.12 + 0.1 * t)
            _, batches = platform('near')
            _, writes = writes_for(camera, batches, {'zclear': None if i % 4 == 3 else 0})
            frames.append(writes)
            names.append(f'motion_{i:02d}')
    cart = {}
    if not args.no_cart:
        rows, prefix = run_cart(frames, vram, args.out)
        model = Frame(vram)
        cart_failures = []
        carried = 0
        for i, (name, writes) in enumerate(zip(names, frames)):
            if not any(o == depth.GPU_ZCLEAR for o, _ in writes):
                # Negative control: the frame drawn over a cleared depth buffer must differ, or
                # the carried-over buffer is not being checked.
                fresh = Frame(vram)
                fresh.gpu = copy.deepcopy(model.gpu)
                cleared = fresh.run([(depth.GPU_ZCLEAR, 0)] + writes)[0]
            picture, stats = model.run(writes)
            if not any(o == depth.GPU_ZCLEAR for o, _ in writes):
                carried += int((cleared != picture).sum())
            if i >= len(rows):
                cart_failures.append({'view': name, 'presented': False})
                continue
            row = rows[i]
            actual = np.array(Image.open(f'{prefix}_{row["tick"]:05d}.ppm').convert('RGB'))
            expected = rgb(picture)
            different = int(np.any(expected != actual, axis=2).sum())
            mismatched = {k: [stats[k], row[k]] for k in depth.STAT_NAMES if stats[k] != row[k]}
            cpu_late = row['cpu_cycles'] > 1000000
            want_ticks = max(1, -(-stats['gpu_cycles'] // 2000000))
            lag_ok = cpu_late or (row['ticks'] == want_ticks and row['gpu_lag'] == want_ticks - 1)
            entry = {'view': name, 'tick': row['tick'], 'different_pixels': different, 'stats': mismatched,
                     'gpu_cycles': row['gpu_cycles'], 'ticks': row['ticks'], 'expected_ticks': want_ticks,
                     'lag_ok': lag_ok, 'cpu_late': cpu_late}
            cart[name] = entry
            if different or mismatched or not lag_ok:
                cart_failures.append(entry)
            if i < len(views) or different:
                Image.fromarray(actual).save(args.out / f'{name}_mei.png')
                sheet(args.out / f'{name}_comparison.png', name,
                      [('reference', expected), ('Mei (cart)', actual), ('difference', diff_image(expected, actual))])
        checks['cart'] = not cart_failures
        if args.motion > 3:
            info['pixels_from_carried_depth'] = carried
            checks['carried_depth_buffer_matters'] = carried > 0
    for r in results:
        r['end_to_end'] = cart.get(r['view'])
        print(json.dumps(r), flush=True)
    for name in names[len(views):]:
        print(json.dumps(cart.get(name)), flush=True)
    report = {'contract': 'docs/RENDERING.md', 'views': results, 'motion': [cart.get(n) for n in names[len(views):]],
              'checks': checks, 'info': info}
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'checks': checks, 'info': info}), flush=True)
    bad = [r['view'] for r in results if r['gpu_only']['framebuffer'] or r['gpu_only']['depth_buffer']
           or r['gpu_only']['display'] or r['gpu_only']['stats']]
    return int(bool(bad) or not all(checks.values()))


if __name__ == '__main__':
    raise SystemExit(main())
