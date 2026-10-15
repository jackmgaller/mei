"""What the dressing scripts of stage 2's cinema, projection booth and staff corridor share
(dress_cinema.py, dress_booth.py, dress_corridor.py): the room's shell from its greybox description
(make_NAME.py's ROOM: walls with their doorways open and lit, the front wall's section, the floor
in textured tiles, the landings beyond the doorways) and the painting of light into its floor and
back wall. The node and painting helpers are level 1's (../arrival/dresskit.py).

Light, as in level 1 and the aquarium: one list of lights per room drives the kit's bake of the lit
props (`lighting.lights`, no shadows, refinement capped) and the painting of the emissive floor and
walls (the kit's formula per texel, with soft shadows from boxes standing in for the props).
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'arrival'))
sys.path.insert(0, str(HERE.parents[1] / 'levels'))
from dresskit import (CUT, Mesh, at, blob, box, font, grid, hex_rgb, kit_lights, noise, r, recipe, rect,  # noqa: E402,F401
                      save_png, shade_plane, smoothstep, text_image, to_image, write_json)
import s2room  # noqa: E402

CUT_H = 1.0
WALL_H = 2.4
WALL_T = 0.25
SLAB = 0.4


def mat_tex(image, color, bits=8, emissive=True, clear=False):
    m = {'color': color, 'texture': {'image': f'art/{image}.png', 'bits': bits, 'projection': 'fit'}}
    if emissive:
        m['class'] = 'emissive'
    return m


def kit_lighting(lights, ambient, refine, direction=(-0.25, 0.7, -0.65), diffuse=0.18):
    out = []
    for L in kit_lights([L for L in lights if not L.get('paint')]):
        L.pop('shadows', None)
        L.pop('radius', None)
        out.append(L)
    return {'direction': list(direction), 'ambient': ambient, 'diffuse': diffuse, 'lights': out, 'refine': refine}


class Room:
    """A greybox description (make_NAME.ROOM) and the dressed shell made from it."""

    def __init__(self, d, prefix):
        self.d = d
        self.P = prefix
        self.X0, self.X1 = d['x']
        self.Z0, self.Z1 = d['z']
        self.XO0, self.XO1 = self.X0 - WALL_T, self.X1 + WALL_T
        self.ZO0, self.ZO1 = self.Z0 - WALL_T, self.Z1 + WALL_T
        self.gaps = {s: sorted(dr['at'] for dr in d['doors'] if dr['side'] == s) for s in 'wen'}

    # ---- the shell

    def floor_tiles(self, nx, nz):
        """The floor in nx x nz tiles, each with its own texture `floor_I_J` (I along x, J along z)."""
        out = []
        xs = np.linspace(self.X0, self.X1, nx + 1)
        zs = np.linspace(self.Z0, self.Z1, nz + 1)
        for i in range(nx):
            for j in range(nz):
                out.append((f'floor_{i}_{j}', xs[i], xs[i + 1], zs[j], zs[j + 1]))
        return out

    def floor_nodes(self, tiles):
        return [box(name, (x0, -0.05, z0), (x1, 0, z1), name, open=['bottom', 'left', 'right', 'back', 'front'])
                for name, x0, x1, z0, z1 in tiles]

    def back_chunks(self, max_len=12.0):
        """The back wall's pieces between its doorways, split into chunks of at most max_len, each
        with its own texture `back_K`: (name, x0, x1)."""
        out = []
        for a, b in s2room.segments(self.XO0, self.XO1, self.gaps['n']):
            n = max(1, int(np.ceil((b - a) / max_len - 1e-6)))
            for k in range(n):
                out.append((a + (b - a) * k / n, a + (b - a) * (k + 1) / n))
        return [(f'back_{k}', a, b) for k, (a, b) in enumerate(out)]

    def wall_nodes(self, chunks):
        P = self.P
        n = []
        # the front wall in section
        m = Mesh()
        m.prism([(self.XO0, -SLAB), (self.XO1, -SLAB), (self.XO1, CUT_H), (self.XO0, CUT_H)], self.ZO0, self.Z0, 'cut',
                back='section', front='wall_in', sides={0: None})
        n.append(m.node('front_wall', 'cut'))
        # the back wall in chunks; a chunk's end is open where it meets the next, cut at the room's
        # ends and a doorway's reveal elsewhere
        edges = [a for _, a, _ in chunks] + [b for _, _, b in chunks]
        for name, a, b in chunks:
            op = ['bottom']
            faces = {'back': name, 'top': 'cut', 'front': 'cut'}
            for side, x in (('left', a), ('right', b)):
                if edges.count(x) > 1:
                    op.append(side)
                elif abs(x - self.XO0) < 1e-6 or abs(x - self.XO1) < 1e-6:
                    faces[side] = 'cut'
                else:
                    faces[side] = 'reveal'
            n.append(box(name + '_wall', (a, -0.02, self.Z1), (b, WALL_H, self.ZO1), 'end', open=op, faces=faces))
        for i, (a, b) in enumerate(self.gaps['n']):
            n.append(box(f'back_lintel_{i}', (a, 2.1, self.Z1), (b, WALL_H - 0.01, self.ZO1), 'end', open=['left', 'right'],
                         faces={'bottom': 'door_glow', 'top': 'cut', 'back': 'lintel', 'front': 'cut'}))
            n.append(box(f'back_sill_{i}', (a, -SLAB, self.Z1), (b, -0.02, self.ZO1), 'cut', open=['top', 'left', 'right', 'back']))
        # the end walls in pieces round their doorways, from the slab up
        for side, (ax0, ax1) in (('w', (self.XO0, self.X0)), ('e', (self.X1, self.XO1))):
            outer = 'left' if side == 'w' else 'right'
            inner = 'right' if side == 'w' else 'left'
            for i, (a, b) in enumerate(s2room.segments(self.Z0, self.Z1, self.gaps[side])):
                op = ['bottom']
                if a == self.Z0:
                    op.append('back')
                if b == self.Z1:
                    op.append('front')
                n.append(box(f'end_{side}_{i}', (ax0, -SLAB, a), (ax1, WALL_H, b), 'end', open=op,
                             faces={'top': 'cut', outer: 'cut', inner: 'end', **({} if 'back' in op else {'back': 'reveal'}),
                                    **({} if 'front' in op else {'front': 'reveal'})}))
            for i, (a, b) in enumerate(self.gaps[side]):
                n.append(box(f'end_{side}_lintel_{i}', (ax0, 2.1, a), (ax1, WALL_H - 0.01, b), 'end', open=['front', 'back'],
                             faces={'bottom': 'door_glow', 'top': 'cut', outer: 'cut', inner: 'lintel'}))
                n.append(box(f'end_{side}_sill_{i}', (ax0, -SLAB, a), (ax1, -0.02, b), 'cut', open=['top', 'front', 'back', inner]))
        return n

    def beyond_nodes(self, door_id, length=1.6, steps=0, rise=0.18, run=0.28, material='beyond'):
        """The way on beyond a doorway: its threshold, a landing and a short flight of steps (steps > 0
        up, < 0 down), so that it reads as leading somewhere."""
        dr = next(x for x in self.d['doors'] if x['id'] == door_id)
        a, b = dr['at']
        m = Mesh()
        if dr['side'] == 'n':
            z0 = self.Z1
            m.quad_y(0.0, a, b, z0, self.ZO1 + length, 1, 'threshold')
            for k in range(abs(steps)):
                y0 = (k + 1) * rise * (1 if steps > 0 else -1)
                za = self.ZO1 + length + k * run
                m.quad_z(za, a, b, min(y0 - (rise if steps > 0 else -rise), y0), max(y0 - (rise if steps > 0 else -rise), y0), -1, 'riser')
                m.quad_y(y0, a, b, za, za + run, 1, material)
            for x, f in ((a, 1), (b, -1)):
                top = WALL_H
                m.quad_x(x, -SLAB, top, self.ZO1, self.ZO1 + length + abs(steps) * run, f, 'beyond_wall')
        else:
            s = 1 if dr['side'] == 'e' else -1
            xw = self.XO1 if s > 0 else self.XO0
            xi = self.X1 if s > 0 else self.X0
            lo, hi = sorted((xi, xw + s * length))
            m.quad_y(0.0, lo, hi, a, b, 1, 'threshold')
            for z, f in ((a, 1), (b, -1)):
                lo2, hi2 = sorted((xw, xw + s * length))
                m.quad_z(z, lo2, hi2, -SLAB, WALL_H, f, 'beyond_wall')
        return [m.node(f'beyond_{door_id}', 'threshold')]

    def shell_materials(self):
        return {'cut': {'color': CUT, 'class': 'emissive'},
                'section': mat_tex(self.P + 'section', '#4a5468', bits=4)}

    def collision(self, name):
        rec = recipe(name, {'floor': {'color': '#8c9098'}}, s2room.shell_nodes(self.d, collision=True), None, 400,
                     collision=True)
        return rec


# ---- painting

def paint_section(xo0, xo1, w=160, h=24):
    """The front wall where the section cuts it, as a drawing shows it: hatched over the floor's
    level, the slab darker under it, the floor's line between."""
    x, y = grid(xo0, xo1, -SLAB, CUT_H, w, h)
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    rgb = np.zeros((h, w, 3)) + np.array([74, 84, 104])
    rgb = np.where((y < 0)[..., None], np.array([50, 57, 72]), rgb)
    rgb = np.where((((i + j) % 6 == 0) & (y >= 0))[..., None], np.array([92, 102, 122]), rgb)
    rgb = np.where((((i - j) % 8 == 0) & (y < 0))[..., None], np.array([62, 70, 86]), rgb)
    rgb = np.where((np.abs(y) < 0.04)[..., None], np.array([150, 160, 178]), rgb)
    rgb = np.where((y > CUT_H - 0.05)[..., None], np.array([118, 132, 158]), rgb)
    return to_image(rgb, dither=0)


def paint_floor(room, x0, x1, z0, z1, base_fn, lights, ambient, blockers, extra_fn=None, w=255, h=None,
                occlusion=0.35):
    """One floor tile: base_fn(x, z) -> rgb in white light, lit by the lights with the blockers'
    soft shadows, darker where it meets the walls, then extra_fn(x, z, rgb) -> rgb (glows)."""
    if h is None:
        h = min(127, int(round(w * (z1 - z0) / (x1 - x0))))
    x, z = grid(x0, x1, z0, z1, w, h)
    base = base_fn(x, z)
    P = np.stack([x.ravel(), np.zeros(x.size), z.ravel()], axis=1)
    lit = shade_plane(P, (0, 1, 0), lights, ambient, blockers).reshape(h, w, 3)
    rgb = base * lit
    d = np.minimum.reduce([x - room.X0, room.X1 - x, z - room.Z0, room.Z1 - z])
    rgb *= (1 - occlusion * np.exp(-np.clip(d, 0, None) / 0.18))[..., None]
    if extra_fn:
        rgb = extra_fn(x, z, rgb)
    return to_image(rgb)


def paint_wall(x0, x1, y0, y1, zface, base_fn, lights, ambient, extra_fn=None, w=255, h=None):
    """A wall facing -z at zface, from x0 to x1 and y0 to y1 (the back wall's chunks)."""
    if h is None:
        h = min(127, max(8, int(round(w * (y1 - y0) / (x1 - x0)))))
    x, y = grid(x0, x1, y0, y1, w, h)
    base = base_fn(x, y)
    P = np.stack([x.ravel(), y.ravel(), np.full(x.size, zface)], axis=1)
    lit = shade_plane(P, (0, 0, -1), [dict(L, shadows=False) for L in lights], ambient).reshape(h, w, 3)
    rgb = base * lit
    rgb *= (1 - 0.3 * np.exp(-np.clip(y, 0, None) / 0.12))[..., None]
    if extra_fn:
        rgb = extra_fn(x, y, rgb)
    return to_image(rgb)


def tile_grid(x, z, size, colour, grout=0.85, var=0.03, seed=0, ox=0.0, oz=0.0, noise_amp=8):
    rng = np.random.default_rng(seed)
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array(colour, dtype=float)
    tid = (np.floor((x - ox) / size) * 31 + np.floor((z - oz) / size) * 17) % 7
    base *= (1 - var * 3 + var * tid)[..., None]
    g = (np.abs(((x - ox) / size) % 1 - 0.5) > 0.5 - 0.06 / size * 0.6) | (np.abs(((z - oz) / size) % 1 - 0.5) > 0.5 - 0.06 / size * 0.6)
    base *= np.where(g, grout, 1.0)[..., None]
    base += (rng.random((h, w)) - 0.5)[..., None] * noise_amp
    return base


def paint_rgb(base, mask, colour):
    return np.where(mask[..., None], np.array(colour, dtype=float), base)
