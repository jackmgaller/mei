"""What the dressing scripts of the aquarium's back of house share (dress_aq_quar.py here,
../aq_plant/dress_aq_plant.py, ../aq_kitchen/dress_aq_kitchen.py): stage 2's shell and painting
(../corridor/s2dress.py, imported, not changed), the passage's shared 8-bit palette
(../passage/diorama.py's quantise_together()), and what these three rooms add:

- the collision companion made from the greybox description as the greybox's own is
  (levels/aquarium/aqroom.py's shell_nodes(collision=True));
- a floor in cells at two heights (walkways over sunken water) on a few painted textures,
  with hand UVs, so that the cells' edges meet end to end and no texture is stretched;
- a flight of steps beyond an end wall's doorway, up or down;
- painting a box of light into a floor (a light entity's box, corners rounded inside it, never
  past it).

Writes nothing itself but through write_json and save_png. Needs NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOMS = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOMS / 'corridor'))
sys.path.insert(0, str(ROOMS.parent / 'levels'))
sys.path.insert(0, str(ROOMS.parent / 'levels' / 'aquarium'))
from s2dress import (CUT_H, SLAB, WALL_H, WALL_T, Mesh, Room, at, blob, box, grid, hex_rgb, kit_lighting,  # noqa: E402,F401
                     mat_tex, paint_floor, paint_rgb, paint_section, paint_wall, r, recipe, rect, save_png,
                     smoothstep, tile_grid, to_image, write_json)
import aqroom  # noqa: E402

sys.path.insert(0, str(ROOMS / 'passage'))
from diorama import quantise_together  # noqa: E402


def used_materials(nodes):
    """The materials nodes name (a box's faces, a mesh's face materials, decals), for pruning a
    recipe's material table."""
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


def prune(materials, nodes):
    used = used_materials(nodes)
    return {k: v for k, v in materials.items() if k in used}


def collision_recipe(d, name):
    """The floor and the walls without tops, exactly as the greybox's companion (aqroom.py)."""
    return recipe(name, {'floor': {'color': '#8c9098'}}, aqroom.shell_nodes(d, collision=True), None, 400,
                  collision=True)


def placements_file(room, ids):
    """ids: [(id, asset, collision)], each placed at the room's origin, yaw 0."""
    return {'format': 'after-hours-placements', 'version': 1, 'room': room,
            'placements': [{'id': i, 'asset': a, 'position': [0, 0, 0], 'collision': c} for i, a, c in ids]}


def save_art(art8, art4, folder):
    """8-bit paintings reduced together to one palette (one 8-bit palette for the room), 4-bit
    ones as they are. art8, art4: {name: PIL image or array}."""
    names = sorted(art8)
    arrays = [np.asarray(art8[n].convert('RGB') if isinstance(art8[n], Image.Image) else art8[n]).astype(float)
              for n in names]
    for n, img in zip(names, quantise_together(arrays)):
        save_png(img, folder / f'{n}.png')
    for n, img in art4.items():
        save_png(img, folder / f'{n}.png')


def vram(art8, art4):
    """Texture bytes as the packer counts them: rows of whole bytes with the one-texel gutter, on
    the 8-texel grid."""
    total = 0
    for imgs, bits in ((art8, 8), (art4, 4)):
        for img in imgs.values():
            w, h = (img.size if isinstance(img, Image.Image) else (img.shape[1], img.shape[0]))
            w8 = -(-(w + 1) // 8) * 8
            h8 = -(-(h + 1) // 8) * 8
            total += w8 * h8 * bits // 8
    return total


# ---- a floor in cells: walkways and water

class UVMesh(Mesh):
    """A mesh of faces looking up (or any faces) with hand UVs from their x and z over a texture
    spanning [x0, x1] x [z0, z1] (row 0 at z1, as grid() paints it)."""

    def __init__(self, span):
        super().__init__()
        self.span = span

    def node(self, id, material):
        n = super().node(id, material)
        x0, x1, z0, z1 = self.span
        n['uvs'] = [[r(min(1.0, max(0.0, (x - x0) / (x1 - x0))), 6), r(min(1.0, max(0.0, (z1 - z) / (z1 - z0))), 6)]
                    for x, y, z in n['vertices']]
        return n


class Cells:
    """A floor on a grid of x and z cuts: each cell is floor (height 0) or sunk (height `sink`,
    water). Tops go to the texture whose span holds the cell's middle; between a floor cell and a
    sunk one, a kerb face looks over the sunk one. Every cut runs the whole grid, so edges meet end
    to end."""

    def __init__(self, xs, zs, is_sunk, sink):
        self.xs = sorted(set(round(v, 4) for v in xs))
        self.zs = sorted(set(round(v, 4) for v in zs))
        self.sink = sink
        self.sunk = [[is_sunk((self.xs[i] + self.xs[i + 1]) / 2, (self.zs[j] + self.zs[j + 1]) / 2)
                      for j in range(len(self.zs) - 1)] for i in range(len(self.xs) - 1)]

    def tops(self, spans, prefix, want_sunk):
        """One UV mesh node per span {name: (x0, x1, z0, z1)} for the cells that are (want_sunk)
        sunk or floor; the node's material is the span's name."""
        nodes = []
        for name, span in spans.items():
            m = UVMesh(span)
            for i in range(len(self.xs) - 1):
                for j in range(len(self.zs) - 1):
                    if self.sunk[i][j] != want_sunk:
                        continue
                    cx, cz = (self.xs[i] + self.xs[i + 1]) / 2, (self.zs[j] + self.zs[j + 1]) / 2
                    if not (span[0] <= cx <= span[1] and span[2] <= cz <= span[3]):
                        continue
                    y = self.sink if want_sunk else 0.0
                    m.quad_y(y, self.xs[i], self.xs[i + 1], self.zs[j], self.zs[j + 1], 1, name)
            if m.faces:
                nodes.append(m.node(f'{prefix}_{name}', name))
        return nodes

    def kerbs(self, id, material, lip=None, lip_h=0.06):
        """The faces between floor cells and sunk ones, looking over the water: `material` from
        the water up to `lip_h` under the floor, `lip` (a painted edge) above it."""
        m = Mesh()
        nx, nz = len(self.xs) - 1, len(self.zs) - 1
        top = 0.0 if lip is None else -lip_h
        for i in range(nx):
            for j in range(nz):
                if self.sunk[i][j]:
                    continue
                for di, dj, face in ((1, 0, 'e'), (-1, 0, 'w'), (0, 1, 'n'), (0, -1, 's')):
                    a, b = i + di, j + dj
                    if not (0 <= a < nx and 0 <= b < nz) or not self.sunk[a][b]:
                        continue
                    for y0, y1, mat in ((self.sink, top, material), (top, 0.0, lip)):
                        if mat is None or y1 <= y0:
                            continue
                        if face in 'ew':
                            x = self.xs[i + 1] if face == 'e' else self.xs[i]
                            m.quad_x(x, y0, y1, self.zs[j], self.zs[j + 1], 1 if face == 'e' else -1, mat)
                        else:
                            z = self.zs[j + 1] if face == 'n' else self.zs[j]
                            m.quad_z(z, self.xs[i], self.xs[i + 1], y0, y1, 1 if face == 'n' else -1, mat)
        return m.node(id, material)


# ---- beyond the end walls' doorways: a landing and a flight of steps

def beyond_flight(R, door_id, steps, landing=0.5, rise=0.2, run=0.28, tread='tread', riser='riser',
                  side_wall='beyond_wall', threshold='threshold', fade=None):
    """Beyond an end wall's doorway (side 'w' or 'e'): its threshold through the wall, a landing,
    then `steps` steps (> 0 up, < 0 down) running on away from the room. fade: a list of tread
    materials, nearest first, for a flight that darkens as it goes (one a step, the last repeated).
    The flight's near wall (the camera's side) looks away from the camera and is not drawn."""
    dr = next(x for x in R.d['doors'] if x['id'] == door_id)
    a, b = dr['at']
    s = 1 if dr['side'] == 'e' else -1
    xi = R.X1 if s > 0 else R.X0
    xw = R.XO1 if s > 0 else R.XO0
    m = Mesh()
    lo, hi = sorted((xi, xw + s * landing))
    m.quad_y(0.0, lo, hi, a, b, 1, threshold)
    up = 1 if steps > 0 else -1
    ys = [0.0]
    x = xw + s * landing
    for k in range(abs(steps)):
        y0, y1 = ys[-1], ys[-1] + up * rise
        # the riser between the last tread and this one, facing back toward the room
        if up > 0:
            m.quad_x(x, y0, y1, a, b, -s, riser)
        lo, hi = sorted((x, x + s * run))
        mat = tread if not fade else fade[min(k, len(fade) - 1)]
        m.quad_y(y1, lo, hi, a, b, 1, mat)
        ys.append(y1)
        x += s * run
    ylo = min(ys) - SLAB
    yhi = max(ys) + WALL_H
    lo, hi = sorted((xw, x))
    # the far side wall, looking back toward the camera
    m.quad_z(b, lo, hi, ylo, yhi, -1, side_wall)
    return m.node(f'beyond_{door_id}', threshold)


# ---- painting

def box_light(x, z, box_, soft=0.18):
    """1 inside a light's box with its corners rounded and its edges eased over `soft` metres
    inside it; 0 outside it, always."""
    x0, z0, x1, z1 = box_
    dx = np.minimum(x - x0, x1 - x)
    dz = np.minimum(z - z0, z1 - z)
    inside = (dx >= 0) & (dz >= 0)
    # a rounded rectangle: distance from the inset rectangle's edge
    ex = np.clip(soft - dx, 0, None)
    ez = np.clip(soft - dz, 0, None)
    d = np.hypot(ex, ez)
    return np.where(inside, 1 - smoothstep(0.0, soft, d), 0.0)


def wet(x, z, cx, cz, rx, rz, seed=0):
    """A wet patch: an irregular soft blob, 0..1."""
    t = np.arctan2(z - cz, x - cx)
    k = 1 + 0.18 * np.sin(t * 3 + seed) + 0.1 * np.sin(t * 5 + seed * 2)
    d = np.hypot((x - cx) / rx, (z - cz) / rz) / k
    return 1 - smoothstep(0.7, 1.0, d)
