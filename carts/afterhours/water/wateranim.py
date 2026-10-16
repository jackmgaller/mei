#!/usr/bin/env python3
"""Agent W's moving water for After Hours (NOTES_W.md): the animated tiles every room with water
shares, and the recipe pieces that use them. The rooms' dress scripts import this file (their
changes are marked "agent W" and listed in NOTES_W.md); run alone it writes the tiles' sheets and
a preview of their frames:

    python3 carts/afterhours/water/wateranim.py [--preview DIR]

How the water moves (NOTES_W.md, "The technique"): every moving thing is a small repeating 4-bit
tile whose frames the Asset Kit keeps in ROM (a sheet's `frames`), copied into the tile in VRAM
when the frame changes (dr_water.akr). Meshes never change. Each tile is seamless in space (it
repeats through a texture window) and in time (its last frame runs into its first), so a loop
has no seam. The tiles are grey; light colours them: an overlay is lit by point lights of its
own (ambient 0), so the moving net is only as bright, and as blue, violet or green, as the light
that falls there.

- CAUSTIC: the net of light a rippled surface throws on the floor, the sand, a wall. Added
  (`add`) over the painted floor, 3 cm up.
- RIPPLE: the glints on a surface seen from above. Added over the painted surface (`add`), or in
  place of a room's still ripple texture (in its blend).
- DRIP: rings spreading on a puddle from drops (the roof's rain, a leak), for puddles.

Deterministic: sums of sines with whole numbers of waves across a tile and of cycles across the
loop; no random numbers.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent

# The tiles: name -> (texels a side, frames, ticks a frame). A frame of a 64-texel 4-bit tile is 2
# KB of ROM and a copy of 64 rows of 32 bytes when it changes.
TILES = {
    'w_caustic': (64, 24, 6),     # 2.4 s a loop, a new frame 10 times a second
    'w_ripple': (64, 16, 6),      # 1.6 s
    'w_drip': (32, 16, 4),        # 1.07 s
    'w_rain': (32, 8, 3),         # 0.4 s: streaks fall two tiles a loop
}

# metres a repeat (power-of-two scales keep the repeats on whole texels: ASSETKIT.md, "Texture tips")
CAUSTIC_SCALE = 2.0               # 32 texels a metre: about a texel a pixel at the game's camera
RIPPLE_SCALE = 2.0
DRIP_SCALE = 1.0
RAIN_SCALE = [0.5, 1.0]           # streaks falling 5 m/s

# a level of light 0..14 -> grey; level 0 is black: it adds nothing
LEVELS = 14
GREY = [(round(255 * (k / LEVELS) ** 1.1), round(255 * (k / LEVELS) ** 1.1), round(255 * (k / LEVELS) ** 1.1))
        for k in range(LEVELS + 1)]

TAU = 2 * math.pi


def _grid(n):
    s = (np.arange(n) + 0.5) / n
    return np.meshgrid(s, s)        # x across (u), z down (v), 0..1 across the tile


def _seeds(count, salt):
    """Fixed seed points in the tile (a golden-ratio sequence) with their wobble's radius, phase
    and cycles a loop (1 or 2, either way round)."""
    g = (math.sqrt(5) - 1) / 2
    out = []
    for i in range(count):
        u = (0.13 + i * g + salt * 0.31) % 1.0
        v = (0.37 + i * g * g * 1.7 + salt * 0.17) % 1.0
        r = 0.035 + 0.03 * ((i * 7 + salt) % 5) / 4
        ph = TAU * ((i * 0.618 + salt * 0.2) % 1.0)
        cyc = (1 + (i % 2)) * (1 if (i * 3 + salt) % 4 < 2 else -1)
        out.append((u, v, r, ph, cyc))
    return out


def caustic(n, f, frames, count=13, salt=0, width=1.6, halo=0.18):
    """The caustic net at frame f: the edges of the cells round seed points that each wobble on a
    small circle a whole number of times a loop (a Voronoi net, wrapped round the tile), the
    edges made wavy by a warp that also loops, brightest where they meet."""
    x, z = _grid(n)
    t = f / frames
    wx = x + 0.035 * np.sin(TAU * (2 * z + t) + 0.7) + 0.02 * np.sin(TAU * (3 * x - 2 * z - t))
    wz = z + 0.035 * np.sin(TAU * (2 * x - t) + 2.1) + 0.02 * np.sin(TAU * (2 * x + 3 * z + t))
    d1 = np.full_like(x, 9.0)
    d2 = np.full_like(x, 9.0)
    for (u, v, r, ph, cyc) in _seeds(count, salt):
        su = u + r * math.cos(ph + TAU * cyc * t)
        sv = v + r * math.sin(ph + TAU * cyc * t)
        dx = (wx - su + 0.5) % 1.0 - 0.5
        dz = (wz - sv + 0.5) % 1.0 - 0.5
        d = np.sqrt(dx * dx + dz * dz)
        d2 = np.where(d < d1, d1, np.minimum(d2, d))
        d1 = np.minimum(d1, d)
    edge = (d2 - d1) * n                 # texels from the cell's edge (about twice)
    line = np.exp(-(edge / width) ** 2)
    glow = np.exp(-edge / 5.0) * halo    # a soft halo, so the net reads as light, not wire
    return np.clip(line * 0.95 + glow, 0, 1)


def ripple(n, f, frames):
    """Glints on a surface seen from above: a fine net of crests (the caustic's cells, smaller and
    other seeds), most of it dark, lit in short stretches where two slow swells rolling across the
    loop crest together."""
    x, z = _grid(n)
    t = f / frames
    net = caustic(n, f, frames, count=30, salt=3, width=0.9, halo=0.0)
    swell = (0.5 + 0.5 * np.sin(TAU * (2 * x + 1 * z - t) + 0.3)) * (0.5 + 0.5 * np.sin(TAU * (1 * x - 2 * z + t) + 1.1))
    lit = np.clip(swell * 1.8 - 0.35, 0, 1) ** 1.3
    return np.clip(net * (0.12 + 0.95 * lit), 0, 1)


def drip(n, f, frames):
    """Rings spreading on a puddle: three drops a loop at fixed places, each ring widening and
    fading, wrapped round the tile."""
    x, z = _grid(n)
    out = np.zeros_like(x)
    drops = [(0.22, 0.30, 0.0), (0.71, 0.62, 0.36), (0.40, 0.84, 0.68)]
    for (dx, dz, t0) in drops:
        age = ((f / frames) - t0) % 1.0
        r = 0.04 + age * 0.42
        ddx = (x - dx + 0.5) % 1.0 - 0.5
        ddz = (z - dz + 0.5) % 1.0 - 0.5
        d = np.sqrt(ddx * ddx + ddz * ddz)
        ring = np.exp(-((d - r) / 0.022) ** 2) * (1 - age) ** 1.5
        out = np.maximum(out, ring)
    return np.clip(out * 1.15, 0, 1)


def rain(n, f, frames):
    """Streaks of rain, each a short slanted line, falling two tiles a loop (so each moves 2n /
    frames texels a frame: rain, not drifting dots)."""
    x, z = _grid(n)                 # z runs down the tile
    out = np.zeros_like(x)
    g = (math.sqrt(5) - 1) / 2
    for i in range(9):
        u = (0.07 + i * g) % 1.0
        v0 = (0.31 + i * g * g * 2.3) % 1.0
        v = (v0 + 2.0 * f / frames) % 1.0
        length = 0.16 + 0.08 * (i % 3)
        dv = (z - v + 0.5) % 1.0 - 0.5          # along the streak, wrapped
        du = (x - u - dv * 0.12 + 0.5) % 1.0 - 0.5
        on = (dv > -length) & (dv < 0) & (np.abs(du) < 0.6 / n)
        out = np.maximum(out, on * (0.45 + 0.55 * (1 + dv / length)))
    return out


FIELDS = {'w_caustic': caustic, 'w_ripple': ripple, 'w_drip': drip, 'w_rain': rain}


def frames_of(name):
    n, frames, _ = TILES[name]
    return [FIELDS[name](n, f, frames) for f in range(frames)]


def levels(c):
    """0..1 -> the tile's 15 grey levels (ordered dither, so the net's thin edges keep their
    shape)."""
    n = c.shape[0]
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5
    d = np.tile(bayer, (n // 4, n // 4))
    return np.clip(np.round(c * LEVELS + d * 0.9), 0, LEVELS).astype(int)


def key(name, color=None, base=None):
    """A tile's key: its field's name, and for a coloured tile the colour's hex (w_ripple_3a90d0),
    or its base's and its colour's (w_ripple_3c8cc8_c0e8ff). A grey tile is coloured by the light;
    a coloured one is for a material whose light is the recipe's ordinary lighting: its colours
    run from black (or the base) to the colour."""
    if color is None:
        return name
    c = color.lstrip('#').lower()
    return f'{name}_{c}' if base is None else f'{name}_{base.lstrip("#").lower()}_{c}'


def _split(k):
    for name in TILES:
        if k == name:
            return name, None
        if k.startswith(name + '_'):
            return name, k[len(name) + 1:]
    raise KeyError(k)


def _rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def sheet(k):
    """The tile's frames side by side, as a grid sheet of n x n cells, frame k at [k, 0]."""
    name, color = _split(k)
    n, frames, _ = TILES[name]
    img = np.zeros((n, n * frames, 3), np.uint8)
    if color is None:
        pal = np.array(GREY, np.uint8)
    else:
        parts = color.split('_')
        c = _rgb(parts[-1])
        b = _rgb(parts[0]) if len(parts) > 1 else np.zeros(3)
        pal = np.array([np.clip(b + (c - b) * min(1.0, 1.3 * j / LEVELS) + 255 * max(0.0, j / LEVELS - 0.75) * 0.8, 0, 255)
                        for j in range(LEVELS + 1)]).round().astype(np.uint8)
    for f, c in enumerate(frames_of(name)):
        img[:, f * n:(f + 1) * n] = pal[levels(c)]
    return Image.fromarray(img, 'RGB')


def write_sheets(art_dir, keys=None):
    """Writes each tile's sheet (KEY.png) into a recipe's art folder; returns the keys."""
    art_dir = Path(art_dir)
    art_dir.mkdir(parents=True, exist_ok=True)
    keys = list(TILES if keys is None else keys)
    for k in keys:
        sheet(k).save(art_dir / f'{k}.png')
    return keys


def sheets_entry(k, art='art'):
    """The recipe's root `sheets` entry for a tile."""
    n = TILES[_split(k)[0]][0]
    return {'image': f'{art}/{k}.png', 'grid': [n, n]}


SCALES = {'w_caustic': CAUSTIC_SCALE, 'w_ripple': RIPPLE_SCALE, 'w_drip': DRIP_SCALE, 'w_rain': RAIN_SCALE}


def texture(k, scale=None, axis='y', offset=None):
    """A material's texture: the tile's frames, repeating (planar along axis)."""
    name = _split(k)[0]
    n, frames, ticks = TILES[name]
    s = scale or SCALES[name]
    if not isinstance(s, (list, tuple)):
        s = [s, s]
    t = {'sheet': k, 'frames': [[f, 0] for f in range(frames)], 'ticks': ticks, 'bits': 4,
         'projection': 'planar', 'axis': axis, 'scale': list(s)}
    if offset:
        t['offset'] = offset
    return t


def material(k, blend='add', color='#406070', **tex):
    """An overlay material: the tile, blended. A grey tile wants the recipe's point lights."""
    return {'color': color, 'blend': blend, 'texture': texture(k, **tex)}


def add_sheets(recipe, keys, art='art'):
    """Adds the tiles' sheets to a recipe's root `sheets`."""
    sh = recipe.setdefault('sheets', {})
    for k in keys:
        sh[k] = sheets_entry(k, art)
    return recipe


def sheet_keys(recipe):
    """The tiles a recipe's materials use (to write their sheets)."""
    out = []
    for m in recipe['materials'].values():
        sh = m.get('texture', {}).get('sheet')
        if sh and sh.startswith('w_') and sh not in out:
            out.append(sh)
    return out


def finish(recipe, art_dir, art='art'):
    """Writes the sheets of the tiles a recipe uses into art_dir and declares them in the recipe."""
    keys = sheet_keys(recipe)
    write_sheets(art_dir, keys)
    return add_sheets(recipe, keys, art)


class Overlay:
    """A recipe of moving water's overlays: flat quads (split into a grid, so the light's corners
    follow its pool) of animated tiles, blended, lit only by point lights of its own (ambient 0:
    where no light falls the tile adds nothing). One per room, placed beside its other recipes.

        ov = Overlay('at_wwater')
        ov.material('glint', 'w_ripple')
        ov.floor('glint', -0.22, x0, x1, z0, z1, nx=3, nz=2)
        ov.light((-1.25, 0.95, 0.0), '#ffd890', 1.8, 2.2)
        write_json(OUT / 'at_wwater.asset.json', ov.recipe(ART))
    """

    def __init__(self, name):
        self.name = name
        self.materials, self.lights = {}, []
        self.vertices, self.faces, self.face_mats = [], [], []
        self.index = {}

    def material(self, name, tile, blend='add', color='#406070', **tex):
        self.materials[name] = material(tile, blend=blend, color=color, **tex)
        return name

    def _v(self, p):
        k = tuple(round(float(c), 5) for c in p)
        if k not in self.index:
            self.index[k] = len(self.vertices)
            self.vertices.append(list(k))
        return self.index[k]

    def _grid(self, mat, corner, du, dv, nu, nv, facing):
        for i in range(nu):
            for j in range(nv):
                q = [[corner[a] + du[a] * (i + di) / nu + dv[a] * (j + dj) / nv for a in range(3)]
                     for (di, dj) in ((0, 0), (1, 0), (1, 1), (0, 1))]
                n = [0.0, 0.0, 0.0]     # Newell's normal, turned to face `facing`
                for k in range(4):
                    a, b = q[k], q[(k + 1) % 4]
                    n[0] += (a[1] - b[1]) * (a[2] + b[2])
                    n[1] += (a[2] - b[2]) * (a[0] + b[0])
                    n[2] += (a[0] - b[0]) * (a[1] + b[1])
                if sum(x * y for x, y in zip(n, facing)) < 0:
                    q.reverse()
                self.faces.append([self._v(p) for p in q])
                self.face_mats.append(mat)

    def floor(self, mat, y, x0, x1, z0, z1, nx=1, nz=1, down=False):
        """A level quad at height y, facing up (seen from above)."""
        self._grid(mat, (x0, y, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0), nx, nz, (0, -1 if down else 1, 0))

    def wall_z(self, mat, z, x0, x1, y0, y1, facing=-1, nx=1, ny=1):
        """An upright quad across x at z, facing -z (toward the camera) or +z."""
        self._grid(mat, (x0, y0, z), (x1 - x0, 0, 0), (0, y1 - y0, 0), nx, ny, (0, 0, facing))

    def wall_x(self, mat, x, z0, z1, y0, y1, facing=1, nz=1, ny=1):
        """An upright quad along z at x, facing +x or -x."""
        self._grid(mat, (x, y0, z0), (0, 0, z1 - z0), (0, y1 - y0, 0), nz, ny, (facing, 0, 0))

    def ellipse(self, mat, y, cx, cz, a, b, n=10):
        """A level ellipse at height y, facing up (a puddle): one polygon of n corners."""
        pts = [(cx + a * math.cos(math.tau * k / n), y, cz + b * math.sin(math.tau * k / n)) for k in range(n)]
        nrm = sum((p[2] - q[2]) * (p[0] + q[0]) for p, q in zip(pts, pts[1:] + pts[:1]))
        if nrm < 0:
            pts.reverse()
        self.faces.append([self._v(p) for p in pts])
        self.face_mats.append(mat)

    def light(self, at, color, intensity, rng, id=None):
        self.lights.append({'id': id or f'w{len(self.lights)}', 'at': [round(float(c), 4) for c in at],
                            'color': color, 'intensity': intensity, 'range': rng})

    def recipe(self, art_dir, art='art', refine=None, triangles=400):
        mesh = {'id': 'water', 'op': 'mesh', 'vertices': self.vertices, 'faces': self.faces,
                'material': self.face_mats[0], 'face_materials': self.face_mats}
        rec = {'format': 'mei-asset', 'version': 1, 'name': self.name,
               'budget': {'vertices': 2048, 'triangles': triangles}, 'materials': self.materials,
               'nodes': [mesh],
               'lighting': {'ambient': 0.0, 'diffuse': 0.0, 'lights': self.lights,
                            'refine': refine or {'tolerance': 20, 'max_added': 48}},
               'verification': {'required': True, 'depth': True, 'perspective': True}}
        return finish(rec, art_dir, art)


def preview(out):
    """Each tile's frames, 4 times, a strip a tile; and the tiles tiled 3 x 3 at frame 0."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in TILES:
        n, frames, _ = TILES[name]
        s = sheet(name)
        s.resize((s.width * 3, s.height * 3), Image.NEAREST).save(out / f'{name}_frames.png')
        cell = s.crop((0, 0, n, n))
        big = Image.new('RGB', (n * 3, n * 3))
        for i in range(3):
            for j in range(3):
                big.paste(cell, (i * n, j * n))
        big.resize((n * 9, n * 9), Image.NEAREST).save(out / f'{name}_tiled.png')


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--preview', metavar='DIR', help='write strips of the frames into DIR')
    a = p.parse_args()
    if a.preview:
        preview(a.preview)
        print('wrote previews into', a.preview)
    else:
        print('tiles:', ', '.join(f'{k} {v[0]}x{v[0]}, {v[1]} frames of {v[2]} ticks' for k, v in TILES.items()))


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
