"""What R1's two aquarium rooms share (dress_aq_hall.py here, ../aq_jelly/dress_aq_jelly.py): the dark
shell of a room from its greybox description (make_aq_NAME.py's ROOM, J's: the walls with their
doorways open on either level, the front wall in section, the floor in painted tiles, the
landings beyond the doorways), the painting of the play file's light boxes into the floor, and one
shared 8-bit palette per room. Node and painting helpers are level 1's (../arrival/dresskit.py).

Light, as the aquarium stage plays it (ROUTE.md, "The rules"): in a dark room the floor looks lit
exactly where a `light` box is. The floor is emissive and painted: inside the boxes (their union,
its edge softened over a few centimetres, the corners a little round) the lamp's glow, outside
them the dark. A light on a cycle is painted at half strength; the runtime's wash shows it on.
The props are lit by the Asset Kit's point lights (`lighting.lights`), which never touch the
floor.

The walls are meshes on one grid per wall (every cell's corners shared), so no edge ends in the
middle of another and the doorways' reveals meet their walls exactly.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
sys.path.insert(0, str(CART / 'rooms' / 'arrival'))
sys.path.insert(0, str(CART / 'levels'))
sys.path.insert(0, str(CART / 'levels' / 'aquarium'))
sys.dont_write_bytecode = True
from dresskit import (Mesh, blob, box, font, grid, hex_rgb, r, rect, save_png, smoothstep,  # noqa: E402,F401
                      to_image, write_json, VERIFY)
import aqroom  # noqa: E402  (J's: imported for the collision companion only)

CUT_H = 1.0
WALL_T = 0.25
SLAB = 0.4
DOOR_H = 2.1
SECTION_CUT = '#3c475e'        # the section's cut faces in a dark room (the ocean gallery's)


def at(node, translate=None, rotate=None, scale=None):
    t = {}
    if scale:
        t['scale'] = [r(c) for c in scale]
    if rotate:
        t['rotate'] = [r(a, 3) for a in rotate]
    if translate:
        t['translate'] = [r(c) for c in translate]
    node['transform'] = t
    return node


def mat_tex(image, color, bits=8, emissive=True, projection='fit', **extra):
    m = {'color': color, 'texture': dict({'image': f'art/{image}.png', 'bits': bits, 'projection': projection}, **extra)}
    if emissive:
        m['class'] = 'emissive'
    return m


def used_materials(nodes):
    used = set()

    def walk(ns):
        for n in ns:
            if 'material' in n:
                used.add(n['material'])
            if isinstance(n.get('faces'), dict):
                used.update(n['faces'].values())
            used.update(n.get('face_materials') or [])
            for d in n.get('decals', []):
                used.add(d['material'])
            walk(n.get('children', []))
    walk(nodes)
    return used


def recipe(name, materials, nodes, lighting=None, triangles=2000, vertices=2048):
    used = used_materials(nodes)
    materials = {k: v for k, v in materials.items() if k in used}
    out = {'format': 'mei-asset', 'version': 1, 'name': name,
           'budget': {'vertices': vertices, 'triangles': triangles}, 'materials': materials, 'nodes': nodes}
    if lighting is not None:
        out['lighting'] = lighting
    out['verification'] = dict(VERIFY)
    return out


def collision(d, name):
    """The greybox's collision companion (the floor, level 1's walks cut into a grid, the walls
    without tops), J's aqroom.shell_nodes(), under the dressed room's name."""
    used = set()

    def walk(ns):
        for n in ns:
            used.add(n['material'])
            walk(n.get('children', []))
    nodes = aqroom.shell_nodes(d, collision=True)
    walk(nodes)
    return {'format': 'mei-asset', 'version': 1, 'name': name, 'budget': {'vertices': 2048, 'triangles': 600},
            'lighting': {'direction': [-0.35, 0.85, -0.45], 'ambient': 0.55},
            'materials': {k: {'color': '#8c9098'} for k in sorted(used)}, 'nodes': nodes}


# ---- the shell

class Shell:
    """A room's walls, floor and doorways from its greybox description. Levels: the floor (0) and,
    when the room has `upper`, level 1; the back and end walls stand to the highest level + 2.4."""

    def __init__(self, d):
        self.d = d
        self.X0, self.X1 = d['x']
        self.Z0, self.Z1 = d['z']
        self.XO0, self.XO1 = self.X0 - WALL_T, self.X1 + WALL_T
        self.ZO0, self.ZO1 = self.Z0 - WALL_T, self.Z1 + WALL_T
        self.U = d.get('upper')
        self.H = (self.U or 0.0) + 2.4
        self.doors = d['doors']

    def level_y(self, lvl):
        return self.U if lvl else 0.0

    # floors

    def floor_tiles(self, nx, nz):
        xs = np.linspace(self.X0, self.X1, nx + 1)
        zs = np.linspace(self.Z0, self.Z1, nz + 1)
        return [(f'floor_{i}_{j}', xs[i], xs[i + 1], zs[j], zs[j + 1]) for i in range(nx) for j in range(nz)]

    def floor_mesh(self, tiles, name='floor'):
        """The floor's tiles as one mesh on a shared grid, each its own material (texture)."""
        m = Mesh()
        for mat, x0, x1, z0, z1 in tiles:
            m.quad_y(0.0, x0, x1, z0, z1, 1, mat)
        return m.node(name, tiles[0][0])

    # walls

    def front_wall(self, section='section', cut='cut'):
        """The front wall where the section cuts it: its face toward the camera in section, its top
        cut at 1 m, from under the slab."""
        m = Mesh()
        m.quad_z(self.ZO0, self.XO0, self.XO1, -SLAB, CUT_H, -1, section)
        m.quad_y(CUT_H, self.XO0, self.XO1, self.ZO0, self.Z0, 1, cut)
        m.quad_x(self.XO0, -SLAB, CUT_H, self.ZO0, self.Z0, -1, cut)
        m.quad_x(self.XO1, -SLAB, CUT_H, self.ZO0, self.Z0, 1, cut)
        return m.node('front_wall', section)

    def end_wall(self, side, inner='end', cut='cut', reveal='reveal', glow='door_glow', sill='threshold'):
        """An end wall (x0..x1 thick) from the slab to the top, with the doorways of every level,
        as one mesh on a z-y grid: the inner face, the top, its front end above the cut (the cut
        wall's edge), the doorways' reveals, lintels and sills."""
        ax0, ax1 = (self.XO0, self.X0) if side == 'w' else (self.X1, self.XO1)
        xin = ax1 if side == 'w' else ax0
        xout = ax0 if side == 'w' else ax1
        sin = 1 if side == 'w' else -1
        gaps = [(dr['at'], self.level_y(dr.get('level', 0))) for dr in self.doors if dr['side'] == side]
        zs = sorted({self.Z0, self.Z1, *[a for (g, _) in gaps for a in g]})
        ys = sorted({-SLAB, CUT_H, self.H, *[y for _, y in gaps], *[y + DOOR_H for _, y in gaps]})
        if self.U is not None:
            ys = sorted(set(ys) | {self.U})

        def filled(i, j):
            zc, yc = (zs[i] + zs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            return not any(g[0] < zc < g[1] and y < yc < y + DOOR_H for g, y in gaps)
        m = Mesh()
        nz, ny = len(zs) - 1, len(ys) - 1
        for i in range(nz):
            for j in range(ny):
                if not filled(i, j):
                    continue
                za, zb, ya, yb = zs[i], zs[i + 1], ys[j], ys[j + 1]
                if yb > 0.0:
                    m.quad_x(xin, max(ya, 0.0) if ya < 0 < yb else ya, yb, za, zb, sin, inner)
                if j == ny - 1:
                    m.quad_y(yb, ax0, ax1, za, zb, 1, cut)
                if i == 0 and ya >= CUT_H - 1e-6:
                    m.quad_z(za, ax0, ax1, ya, yb, -1, cut)
                if j + 1 < ny and not filled(i, j + 1):
                    m.quad_y(yb, ax0, ax1, za, zb, 1, sill)             # a doorway's sill
                if j > 0 and not filled(i, j - 1):
                    m.quad_y(ya, ax0, ax1, za, zb, -1, glow)            # a lintel's underside
                if i + 1 < nz and not filled(i + 1, j):
                    m.quad_z(zb, ax0, ax1, ya, yb, 1, reveal)
                if i > 0 and not filled(i - 1, j):
                    m.quad_z(za, ax0, ax1, ya, yb, -1, reveal)
        # the outer face is never seen (the void's side); the wall's foot below the floor is the slab
        del xout
        return m.node(f'end_{side}', inner)

    def back_wall(self, bands, cut='cut'):
        """The back wall (no doorways in R1's rooms) as one mesh: bands [(y0, y1, [(x0, x1,
        material)])] up its room face, sharing their edges; the top cut."""
        m = Mesh()
        for y0, y1, pieces in bands:
            for x0, x1, mat in pieces:
                m.quad_z(self.Z1, x0, x1, y0, y1, -1, mat)
        xs = sorted({a for _, _, ps in bands for p in ps for a in p[:2]})
        top = max(b[1] for b in bands)
        for a, b in zip(xs, xs[1:]):
            m.quad_y(top, a, b, self.Z1, self.ZO1, 1, cut)
        return m.node('back_wall', bands[0][2][0][2])

    def beyond(self, door_id, length=1.4, walls_h=2.3, floor='threshold', far='beyond_floor', wall='beyond_wall',
               extra=None):
        """The way on beyond a doorway: the floor out beyond the wall (`far`; the doorway's own is
        its wall's sill) and the passage's two sides, so the doorway reads as leading somewhere (an
        end door; level 1's at `upper`). extra(mesh, x0, x1, z0, z1, y, s) adds to it (s: +1 east)."""
        dr = next(x for x in self.doors if x['id'] == door_id)
        a, b = dr['at']
        y = self.level_y(dr.get('level', 0))
        s = 1 if dr['side'] == 'e' else -1
        xw = self.XO1 if s > 0 else self.XO0
        xi = self.X1 if s > 0 else self.X0
        m = Mesh()
        del xi
        lo2, hi2 = sorted((xw, xw + s * length))
        m.quad_y(y, lo2, hi2, a, b, 1, far)
        for z, f in ((a, 1), (b, -1)):
            m.quad_z(z, lo2, hi2, y - SLAB if y == 0 else y - 0.15, y + walls_h, f, wall)
        if extra:
            extra(m, lo2, hi2, a, b, y, s)
        return m.node(f'beyond_{door_id}', far)


# ---- painting

def to15(a):
    """8-bit RGB as the GPU's 15-bit colour shows it, back in 8 bits."""
    q = (np.asarray(a).astype(int) * 31 + 127) // 255
    return (q * 255 + 15) // 31


def quantise_together(images, colours=255):
    """Several 8-bit paintings (RGB or RGBA; alpha below a half is a hole) reduced to one shared set
    of at most `colours` 15-bit colours, so a room's 8-bit textures take one 8-bit palette."""
    arrays, alphas = [], []
    for img in images:
        a = np.asarray(img.convert('RGBA'))
        arrays.append(a[..., :3])
        alphas.append(a[..., 3] >= 128)
    flat = np.concatenate([to15(a).reshape(-1, 3) for a, al in zip(arrays, alphas)], axis=0)
    keep = np.concatenate([al.reshape(-1) for al in alphas])
    strip = Image.fromarray(flat[keep].reshape(1, -1, 3).astype(np.uint8), 'RGB')
    q = strip.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = to15(np.array(q.getpalette()[:colours * 3]).reshape(-1, 3))
    mapped = np.zeros_like(flat)
    mapped[keep] = pal[np.array(q).reshape(-1)]
    out, k = [], 0
    for a, al in zip(arrays, alphas):
        n = a.shape[0] * a.shape[1]
        rgb = mapped[k:k + n].reshape(a.shape).astype(np.uint8)
        k += n
        if al.all():
            out.append(Image.fromarray(rgb, 'RGB'))
        else:
            out.append(Image.fromarray(np.dstack([rgb, np.where(al, 255, 0).astype(np.uint8)]), 'RGBA'))
    return out


def box_sdf(x, z, b):
    """Signed distance (metres, negative inside) to a box (x0, z0, x1, z1) in plan."""
    cx, cz = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    hx, hz = (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
    qx, qz = np.abs(x - cx) - hx, np.abs(z - cz) - hz
    return np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0)


def lit_mask(x, z, boxes, soft=0.07):
    """1 inside the union of the light boxes, 0 outside, over `soft` metres each side of the edge
    (the outer corners come out a little round)."""
    if not boxes:
        return np.zeros_like(x)
    d = np.min([box_sdf(x, z, b) for b in boxes], axis=0)
    return 1 - smoothstep(-soft, soft, d)


def caustics(x, z, scale=1.0, seed=0.0):
    """A caustic net: bright thin lines, 0..1 (the ocean gallery's)."""
    x = x * scale
    z = z * scale
    a = np.sin(x * 2.1 + np.sin(z * 1.7 + seed) * 1.4 + seed)
    b = np.sin(z * 2.6 + np.sin(x * 1.3 - seed) * 1.2 - seed * 0.5)
    c = np.sin((x + z) * 1.6 + np.sin((x - z) * 1.1 + seed) * 1.1)
    v = (a + b + c) / 3.0
    return np.clip(1 - np.abs(v) * 2.6, 0, 1) ** 3


def stone(x, z, colour, size, seed, grout=0.72, var=0.05, fleck=10.0):
    """Polished stone in square slabs, in white light: a little variation per slab, flecks, dark
    joints."""
    rng = np.random.default_rng(seed)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array(colour, dtype=float)
    ix, iz = np.floor(x / size), np.floor(z / size)
    tid = (ix * 73 + iz * 151) % 11
    base *= (1 - var + 2 * var * tid / 10)[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * fleck
    fx, fz = (x / size) % 1, (z / size) % 1
    joint = (np.minimum(fx, 1 - fx) * size < 0.018) | (np.minimum(fz, 1 - fz) * size < 0.018)
    base *= np.where(joint, grout, 1.0)[..., None]
    return base


def paint_section(xo0, xo1, w=200, h=20, face=(46, 52, 68), hatch=(62, 70, 90), slab=(30, 34, 46)):
    """The front wall where the section cuts it, as a drawing shows it, in a dark room's tones:
    hatched over the floor's level, the slab darker under it, the floor's line between."""
    x, y = grid(xo0, xo1, -SLAB, CUT_H, w, h)
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    rgb = np.zeros((h, w, 3)) + np.array(face)
    rgb = np.where((y < 0)[..., None], np.array(slab), rgb)
    rgb = np.where((((i + j) % 6 == 0) & (y >= 0))[..., None], np.array(hatch), rgb)
    rgb = np.where((((i - j) % 8 == 0) & (y < 0))[..., None], np.array(hatch) * 0.7, rgb)
    rgb = np.where((np.abs(y) < 0.04)[..., None], np.array([96, 110, 136]), rgb)
    rgb = np.where((y > CUT_H - 0.05)[..., None], np.array([84, 98, 124]), rgb)
    return to_image(rgb, dither=0)


def ring(id, cx, cz, y0, y1, r_out, r_in, segments, material, inner=None):
    """A rim round a glass: its outer wall and its top as a flat annulus (and with `inner`, its
    inner wall, facing in), as one mesh."""
    m = Mesh()
    pts = [(math.cos(math.tau * i / segments), math.sin(math.tau * i / segments)) for i in range(segments)]
    for i in range(segments):
        (c0, s0), (c1, s1) = pts[i], pts[(i + 1) % segments]
        mx, mz = (c0 + c1) / 2, (s0 + s1) / 2
        m.poly([(cx + r_out * c0, y0, cz + r_out * s0), (cx + r_out * c1, y0, cz + r_out * s1),
                (cx + r_out * c1, y1, cz + r_out * s1), (cx + r_out * c0, y1, cz + r_out * s0)], (mx, 0, mz), material)
        m.poly([(cx + r_out * c0, y1, cz + r_out * s0), (cx + r_out * c1, y1, cz + r_out * s1),
                (cx + r_in * c1, y1, cz + r_in * s1), (cx + r_in * c0, y1, cz + r_in * s0)], (0, 1, 0), material)
        if inner:
            m.poly([(cx + r_in * c0, y0, cz + r_in * s0), (cx + r_in * c1, y0, cz + r_in * s1),
                    (cx + r_in * c1, y1, cz + r_in * s1), (cx + r_in * c0, y1, cz + r_in * s0)], (-mx, 0, -mz), inner)
    return m.node(id, material)
