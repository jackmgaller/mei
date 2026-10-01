#!/usr/bin/env python3
"""Generates the demo cart's assets in carts/demo/:
  cube.bin   - a textured, Gouraud-shaded cube (6 quads)
  ground.bin - a 16x16 checkerboard of flat quads
  tex.bin    - a 4-bit 32x32 brick texture for slot 0 (stride 128 bytes, 32 rows)
  pal.bin    - its 16-colour palette (15-bit colours)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meshlib import Mesh, rgb

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'carts', 'demo')

def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

# ---- cube: each face seen from outside has corners BL, BR, TL, TR (strip order)
cube = Mesh()
faces = [((0, 0, -1), (0, 1, 0)), ((0, 0, 1), (0, 1, 0)), ((-1, 0, 0), (0, 1, 0)),
         ((1, 0, 0), (0, 1, 0)), ((0, 1, 0), (0, 0, 1)), ((0, -1, 0), (0, 0, -1))]
shade = [rgb(160, 160, 160), rgb(90, 90, 90), rgb(120, 120, 120), rgb(140, 140, 140),
         rgb(176, 176, 176), rgb(70, 70, 70)]
for (n, up), s in zip(faces, shade):
    fwd = tuple(-c for c in n)
    right = cross(up, fwd)
    corners = []
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        p = tuple(n[i] + right[i] * dx + up[i] * dy for i in range(3))
        corners.append(cube.vertex(*p))
    # Gouraud: brighter at the top of each face, a warm tint on one corner
    cols = [s, s, rgb(min(255, (s & 255) + 60), min(255, (s & 255) + 50), min(255, (s & 255) + 30)),
            rgb(min(255, (s & 255) + 40), min(255, (s & 255) + 40), min(255, (s & 255) + 40))]
    cube.quad(corners, cols, [(0, 31), (31, 31), (0, 0), (31, 0)], slot=0, four_bit=True, palette=0)
open(os.path.join(out, 'cube.bin'), 'wb').write(cube.pack())

# ---- ground: 16 x 16 tiles of 2 units at y = -1.5
g = Mesh()
N, S, Y = 16, 2.0, -1.5
idx = {}
for j in range(N + 1):
    for i in range(N + 1):
        idx[i, j] = g.vertex((i - N / 2) * S, Y, (j - N / 2) * S)
for j in range(N):
    for i in range(N):
        c = rgb(70, 120, 60) if (i + j) % 2 == 0 else rgb(50, 90, 45)
        # seen from above: BL = (i, j), BR = (i+1, j), TL = (i, j+1), TR = (i+1, j+1)
        g.quad([idx[i, j], idx[i + 1, j], idx[i, j + 1], idx[i + 1, j + 1]], [c])
open(os.path.join(out, 'ground.bin'), 'wb').write(g.pack())

# ---- texture: 32x32 bricks, 4-bit, rows 128 bytes apart
tex = bytearray(128 * 32)
for y in range(32):
    for x in range(32):
        row = y // 8
        mortar = y % 8 == 7 or (x + (4 if row % 2 else 0)) % 16 == 15
        c = 1 if mortar else 2 + ((x * 7 + y * 13 + row * 5) % 5)
        tex[y * 128 + x // 2] |= c << ((x & 1) * 4)
open(os.path.join(out, 'tex.bin'), 'wb').write(bytes(tex))

def c15(r, g, b):
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
pal = [0, c15(200, 200, 190), c15(170, 70, 50), c15(185, 80, 55), c15(160, 64, 48), c15(196, 92, 60),
       c15(150, 60, 45)] + [0] * 9
open(os.path.join(out, 'pal.bin'), 'wb').write(struct.pack('<16H', *pal))
print('wrote cube.bin ground.bin tex.bin pal.bin to', out)
