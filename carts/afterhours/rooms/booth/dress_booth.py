#!/usr/bin/env python3
"""Stage 2, the projection booth, dressed: writes the room's Asset Kit recipes into dressed/, their
textures into dressed/art/ and (with --placements) booth.placements.json beside this script; without
it, a draft in dressed/draft.placements.json, which ../corridor/capture.py prefers while it exists.

    python3 carts/afterhours/rooms/booth/dress_booth.py --placements

A long low room over the back of the cinema, the last reel running to nobody. The two 35 mm machines
are cut at 1 m, and the section shows their insides: the lamp house glowing orange, the film's
path, the reels. Their beams cross the dark to the ports in the west wall. Also here:

- the rewind bench under its work lamp, with two reels standing on their rewinds, a splicer and
  cans;
- the racks of film cans against the back wall;
- two posters of old films, as shapes;
- a red light over the door that says a show is running;
- the stair down to the corridor beyond the door.

The floor plan is the level lead's (PLAN.md, make_booth.py), imported for its numbers. Light as in
../corridor/s2dress.py; the beams are their own recipe, unlit and additive. Everything named is
fictional. Needs NumPy and Pillow.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'corridor'))
import make_booth as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from s2dress import (CUT_H, WALL_H, Mesh, Room, at, blob, box, grid, kit_lighting, mat_tex, paint_floor,  # noqa: E402
                     paint_rgb, paint_section, paint_wall, recipe, rect, save_png, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'pb_'
R = Room(G.ROOM, P)
BX0, BZ0, BX1, BZ1 = G.BENCH
KX0, KZ0, KX1, KZ1 = G.RACKS
PORTS = (0.1, 0.95)                    # the ports' z in the west wall, one a machine
REWINDS = (-4.4, -2.6)
POSTERS = ((-1.3, -0.3), (0.3, 1.3))   # x0, x1 on the back wall, y 1.0 .. 1.9
AMBIENT = 0.1


def lamp_at(k):
    x0, z0, x1, z1 = G.PROJECTORS[k]
    return [x1 - 0.25, 1.15, (z0 + z1) / 2]


def lights():
    return [
        {'id': 'lamp_0', 'at': lamp_at(0), 'color': '#ffa048', 'intensity': 1.7, 'range': 3.2, 'shadows': True},
        {'id': 'lamp_1', 'at': lamp_at(1), 'color': '#ffa048', 'intensity': 1.7, 'range': 3.2, 'shadows': True},
        {'id': 'bench', 'at': [-3.7, 1.9, 2.55], 'color': '#ffdcaa', 'intensity': 1.8, 'range': 3.0, 'shadows': True},
        {'id': 'tube', 'at': [1.5, 2.5, -1.3], 'color': '#dce8f0', 'intensity': 1.3, 'range': 4.8, 'line': 1.2, 'shadows': True},
        {'id': 'tube_w', 'at': [-3.5, 2.5, -1.6], 'color': '#dce8f0', 'intensity': 0.9, 'range': 4.4, 'line': 1.2, 'shadows': True},
        {'id': 'door', 'at': [R.XO1 + 0.7, 1.4, -1.8], 'color': '#e4eef8', 'intensity': 1.6, 'range': 2.8, 'shadows': True},
        {'id': 'show_light', 'at': [5.2, 2.15, R.Z1 - 0.15], 'color': '#ff3030', 'intensity': 0.6, 'range': 1.6, 'paint': True},
        {'id': 'ports', 'at': [R.X0 + 0.15, 1.2, 0.5], 'color': '#7088c0', 'intensity': 0.5, 'range': 2.0, 'paint': True},
    ]


def blockers():
    out = [(x0, 0, z0, x1, 1.6, z1) for (x0, z0, x1, z1) in G.PROJECTORS]
    out += [(BX0, 0, BZ0, BX1, 0.9, BZ1), (KX0, 0, KZ0, KX1, 2.0, KZ1)]
    return out


# ---- painting

def floor_base(x, z):
    h, w = x.shape
    rng = np.random.default_rng(21)
    base = np.zeros((h, w, 3)) + np.array([118, 128, 120]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    # worn bare where he walks round the west machine
    for (ax, az, bx, bz) in ((-5.0, -1.4, -1.8, -1.4), (-5.0, -1.4, -5.0, 1.6), (-5.0, 1.6, -1.8, 1.6), (-1.8, 1.6, -1.8, -1.4)):
        seg = rect(x, z, min(ax, bx) - 0.3, min(az, bz) - 0.3, max(ax, bx) + 0.3, max(az, bz) + 0.3, soft=0.2)
        base = base * (1 - 0.12 * seg)[..., None] + seg[..., None] * np.array([12, 10, 6])
    # a rubber mat between the machines, and scraps of film leader
    base = paint_rgb(base, rect(x, z, -2.9, -0.2, -0.1, 0.8) > 0, (52, 54, 58))
    for k in range(10):
        sx, sz = -5.5 + rng.random() * 10, -2.6 + rng.random() * 4.6
        strip = (np.abs((x - sx) * 0.6 + (z - sz) * 0.8) < 0.025) & (np.hypot(x - sx, z - sz) < 0.35)
        base = paint_rgb(base, strip, (60, 40, 30) if k % 3 else (200, 190, 150))
    return base


def floor_extra(x, z, rgb):
    for k in range(2):   # each lamp house leaks light through its vents onto the floor round it
        lx, _, lz = lamp_at(k)
        rgb = rgb + (blob(x, z, lx, lz, 0.9, 1.0) * 0.18)[..., None] * np.array([255, 140, 60])
    return rgb


def wall_base(x, y):
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([150, 150, 140])
    base = np.where((y < 1.0)[..., None], np.array([110, 120, 110]), base)
    base = np.where((np.abs(y - 1.0) < 0.02)[..., None], np.array([70, 70, 66]), base)
    # two posters of old films: a moon over a sea; a road at sunset
    p0, p1 = POSTERS
    sea = rect(x, y, p0[0], 1.0, p0[1], 1.9) > 0
    base = paint_rgb(base, sea, (30, 50, 110))
    base = paint_rgb(base, sea & (y < 1.3), (40, 90, 150))
    base = paint_rgb(base, blob(x, y, (p0[0] + p0[1]) / 2 + 0.15, 1.65, 0.12) > 0.5, (250, 240, 200))
    road = rect(x, y, p1[0], 1.0, p1[1], 1.9) > 0
    base = paint_rgb(base, road, (230, 120, 60))
    base = paint_rgb(base, road & (y > 1.55), (250, 190, 90))
    base = paint_rgb(base, road & (y < 1.25), (60, 50, 60))
    base = paint_rgb(base, road & (np.abs(x - (p1[0] + p1[1]) / 2) < (1.25 - y) * 0.8) & (y < 1.25), (110, 100, 100))
    for (a, b) in POSTERS:
        fr = rect(x, y, a - 0.04, 0.96, b + 0.04, 1.94) * (1 - rect(x, y, a, 1.0, b, 1.9))
        base = paint_rgb(base, fr > 0, (40, 36, 34))
    return base


def wall_extra(x, y, rgb):
    rgb = rgb + (blob(x, y, 5.2, 2.15, 0.4, 0.22) * 0.4)[..., None] * np.array([255, 50, 40])
    rgb = rgb + (blob(x, y, -3.7, 1.95, 1.2, 0.5) * 0.15)[..., None] * np.array([255, 210, 150])
    return rgb


def paint_projector_top(w=16, h=28):
    """A projector in section, from above (west to the left): the lamp house's glow at the east end,
    the gate and lens at the west, the film's path, the reels' cut circles."""
    img = Image.new('RGB', (w, h), (118, 132, 158))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, w - 2, h - 2], fill=(40, 44, 50))
    d.ellipse([w - 10, h // 2 - 4, w - 2, h // 2 + 4], fill=(255, 150, 50))
    d.ellipse([w - 8, h // 2 - 2, w - 4, h // 2 + 2], fill=(255, 236, 170))
    d.ellipse([2, 2, 10, 10], outline=(160, 166, 176))
    d.ellipse([2, h - 11, 10, h - 3], outline=(160, 166, 176))
    d.line([(6, 10), (5, h // 2), (6, h - 11)], fill=(120, 80, 50))
    d.rectangle([0, h // 2 - 2, 3, h // 2 + 2], fill=(150, 170, 220))
    return img


def paint_bench_top(w=64, h=10):
    """The rewind bench from above: a light box for checking film, a splicer, cans, a reel of leader."""
    img = Image.new('RGB', (w, h), (120, 110, 96))
    d = ImageDraw.Draw(img)
    d.rectangle([22, 2, 34, 7], fill=(240, 236, 220))
    d.line([(22, 4), (34, 4)], fill=(120, 90, 60))
    d.rectangle([40, 3, 46, 6], fill=(70, 74, 80))
    for k, cx in enumerate((52, 58)):
        d.ellipse([cx - 3, 2, cx + 3, 8], fill=(170, 176, 186), outline=(110, 116, 126))
    d.rectangle([4, 6, 9, 8], fill=(200, 60, 50))
    return img


def paint_racks(w=48, h=40):
    """The racks' front: shelves of film cans on edge, silver, some labelled in colours."""
    img = Image.new('RGB', (w, h), (60, 62, 66))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(8)
    for row in range(5):
        y0 = 2 + row * 8
        d.rectangle([0, y0 + 6, w, y0 + 7], fill=(120, 124, 130))
        x = 1
        while x < w - 3:
            cw = 2 + int(rng.integers(0, 2))
            col = (170 + int(rng.integers(0, 40)),) * 3
            d.rectangle([x, y0, x + cw - 1, y0 + 5], fill=col)
            if rng.random() < 0.25:
                d.rectangle([x, y0 + 2, x + cw - 1, y0 + 3], fill=[(200, 60, 50), (60, 110, 200), (230, 190, 60)][int(rng.integers(0, 3))])
            x += cw + 1
    return img


def paint_reel(n=16):
    img = Image.new('RGB', (n, n), (150, 156, 166))
    d = ImageDraw.Draw(img)
    d.ellipse([3, 3, n - 4, n - 4], fill=(60, 44, 34))
    d.ellipse([6, 6, n - 7, n - 7], fill=(150, 156, 166))
    for k in range(3):
        d.line([(n // 2, n // 2), (n // 2 + [5, -4, -1][k], n // 2 + [1, 3, -5][k])], fill=(110, 116, 126))
    return img


def paint_port(w=8, h=8):
    img = Image.new('RGB', (w, h), (40, 50, 80))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, w - 2, h - 2], fill=(150, 170, 230))
    d.rectangle([2, 2, w - 3, h - 3], fill=(220, 230, 255))
    return img


# ---- the recipes

def projector_nodes(k):
    x0, z0, x1, z1 = G.PROJECTORS[k]
    zc = (z0 + z1) / 2
    n = [box(f'proj_{k}_base', (x0 + 0.08, -0.02, z0 + 0.15), (x1 - 0.08, 0.55, z1 - 0.15), 'pedestal', open=['bottom']),
         box(f'proj_{k}_body', (x0, 0.54, z0), (x1, CUT_H, z1), 'machine', open=['bottom'], faces={'top': 'proj_top'}),
         at({'id': f'proj_{k}_lens', 'op': 'cylinder', 'radius': 0.07, 'height': 0.18, 'segments': 6, 'material': 'lens',
             'faces': {'top': 'glass_lens'}}, translate=[x0 - 0.08, 0.86, zc - 0.25], rotate=[0, 0, 90])]
    return n


def room_recipe():
    tiles = R.floor_tiles(1, 1)
    chunks = R.back_chunks(13.0)
    m = R.shell_materials()
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#5a6460')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#8a8a82')
    m.update({
        'wall_in': {'color': '#7a8078'}, 'end': {'color': '#9a9a90'}, 'reveal': {'color': '#8a8a80'},
        'lintel': {'color': '#7a7a72'}, 'door_glow': {'color': '#e0e8f0', 'class': 'emissive'},
        'threshold': {'color': '#7e8288', 'class': 'emissive'}, 'beyond_wall': {'color': '#3a4048', 'class': 'emissive'},
        'beyond': {'color': '#8a8e94', 'class': 'emissive'}, 'riser': {'color': '#4a5058', 'class': 'emissive'},
        'pedestal': {'color': '#5a6470'}, 'machine': {'color': '#7a8494'},
        'proj_top': mat_tex(P + 'proj_top', '#6a6060'), 'lens': {'color': '#2a2c30'},
        'glass_lens': {'color': '#c0d0ff', 'class': 'emissive'},
        'bench': {'color': '#8a7a66'}, 'bench_top': mat_tex(P + 'bench_top', '#8a8070', emissive=False),
        'rewind': {'color': '#6a6e76'}, 'reel': mat_tex(P + 'reel', '#8a8a90', bits=4, emissive=False),
        'reel_edge': {'color': '#9aa0a8'},
        'racks': {'color': '#5a5e64'}, 'racks_front': mat_tex(P + 'racks', '#7a7c80', emissive=False),
        'racks_top': {'color': '#4a4e54'},
        'port': mat_tex(P + 'port', '#a0b4e8', bits=4), 'show': {'color': '#ff3a30', 'class': 'emissive'},
        'frame': {'color': '#4a4a50'},
    })
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks) + R.beyond_nodes('corridor', 1.4)
    n += projector_nodes(0) + projector_nodes(1)
    n.append(box('bench', (BX0, -0.02, BZ0), (BX1, 0.9, R.Z1), 'bench', open=['bottom', 'front'], faces={'top': 'bench_top'}))
    for k, x in enumerate(REWINDS):
        n.append(box(f'rewind_{k}', (x - 0.03, 0.89, 2.66), (x + 0.03, 1.22, 2.74), 'rewind', open=['bottom']))
        n.append(at({'id': f'reel_{k}', 'op': 'cylinder', 'radius': 0.27, 'height': 0.05, 'segments': 10, 'material': 'reel_edge',
                     'faces': {'top': 'reel', 'bottom': 'reel'}}, translate=[x, 1.2, 2.62], rotate=[90, 0, 0]))
    n.append(box('racks', (KX0, -0.02, KZ0), (KX1, 2.0, R.Z1), 'racks', open=['bottom', 'front'],
                 faces={'back': 'racks_front', 'top': 'racks_top'}))
    # the ports in the west wall, lit by the beams going through them
    for k, z in enumerate(PORTS):
        n.append(box(f'port_{k}', (R.X0 - 0.02, 0.95, z - 0.18), (R.X0 + 0.03, 1.3, z + 0.18), 'frame', open=['left'],
                     faces={'right': 'port'}))
    n.append(box('show_light', (5.05, 2.05, R.Z1 - 0.06), (5.35, 2.22, R.Z1 + 0.02), 'show', open=['front']))
    return recipe(P + 'room', m, n, kit_lighting(lights(), AMBIENT, {'tolerance': 22, 'max_added': 220}), 1600)


def beams_recipe():
    """The two beams from the lenses to the ports: additive sheets, unlit."""
    m = {'beam': {'color': '#141a30', 'blend': 'add'}}
    a = Mesh()
    for k, zp in enumerate(PORTS):
        x0, z0, x1, z1 = G.PROJECTORS[k]
        lx, ly, lz = x0 - 0.17, 0.86 if k == 0 else 1.15, (z0 + z1) / 2 - 0.25
        a.poly([(lx, ly, lz), (R.X0 + 0.04, 1.06, zp - 0.15), (R.X0 + 0.04, 1.2, zp + 0.15)], (0, 1, 0), 'beam')
    return recipe(P + 'beams', m, [a.node('beams', 'beam')], {'bake': False}, 10)


def main():
    L = lights()
    blk = blockers()
    art = {}
    for name, x0, x1, z0, z1 in R.floor_tiles(1, 1):
        art[P + name] = paint_floor(R, x0, x1, z0, z1, floor_base, L, AMBIENT, blk, floor_extra)
    for name, a, b in R.back_chunks(13.0):
        art[P + name] = paint_wall(a, b, 0.0, WALL_H, R.Z1, wall_base, L, AMBIENT, wall_extra)
    art.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'proj_top': paint_projector_top(),
                P + 'bench_top': paint_bench_top(), P + 'racks': paint_racks(), P + 'reel': paint_reel(), P + 'port': paint_port()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (room_recipe(), beams_recipe(), R.collision(P + 'room_col')):
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'beams', 'asset': P + 'beams', 'position': [0, 0, 0], 'collision': 'none'}]
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'booth', 'placements': placements}
    write_json(HERE / 'booth.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
