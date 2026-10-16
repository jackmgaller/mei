#!/usr/bin/env python3
"""The aquarium, room 2: the jellyfish gallery, dressed. Writes the room's Asset Kit recipes into
dressed/, their textures into dressed/art/ and (with --placements) aq_jelly.placements.json
beside this script; without it, a draft in dressed/draft.placements.json, which the capture
prefers while it exists.

    python3 carts/afterhours/rooms/aq_jelly/dress_aq_jelly.py --placements

A narrow, almost black gallery. Down its middle stand four slender glass columns of jellyfish,
each on a lacquered plinth with its lamp in it, each bay its own hue from the west: blue, violet,
pink, pale aqua. The lamps' cycle (PLAN.md: each on 240 ticks of 480, 120 after the one west of
it) is the runtime's wash over the bays; the floor is polished black stone painted with each bay's
hue at half strength, brightest under its column, with the column's reflection running toward the
camera, so a bay reads lit when the wash is on and dim when it is off. The ends beyond the bays
are never lit. Along the back, a band of small wall tanks: moon jellies, upside-down jellies,
seahorses, garden eels, anemones. The doorways: the great tank's blue to the west, the ocean
gallery's light to the east.

The floor plan is the level lead's (PLAN.md, make_aq_jelly.py, imported for its numbers only).
Everything is emissive or lit by the kit's directional light alone (no point lights: nothing here
needs refinement). Needs NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'aq_hall'))
import make_aq_jelly as G  # noqa: E402  (J's plan: imported for its numbers only)
from aqdress import (CUT_H, SECTION_CUT, Mesh, Shell, at, blob, box, caustics, collision, lit_mask,  # noqa: E402
                     mat_tex, paint_section, quantise_together, r, recipe, ring, save_png, smoothstep, stone,
                     to_image, write_json)

sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'aj_'
S = Shell(G.ROOM)
COLS = G.COLS
HUES = ['#7c90ff', '#b47cff', '#ff80c8', '#80ece0']        # the bays' lamps, west to east
BAYS = [b for _, b, _, _ in G.ROOM['lights']]
TANKS = (-5.5, 3.6, 5.5, 4.0)                               # the wall tanks' footprint
TANK_Y1 = 0.98                                              # their band's top (cut at 1 m)
COL_R = 0.45                                                # the glass, inside the 1 m square
COL_TOP = 2.3
PLINTH_H = 0.22
TEX_M = 28                                                  # the floor's texels a metre


def hue(k, scale=1.0):
    c = np.array([int(HUES[k][i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    return c * scale


def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, round(c)))) for c in rgb)


# ---- painting

def paint_floor_tile(x0, x1, z0, z1):
    w = int(round((x1 - x0) * TEX_M))
    h = min(127, int(round((z1 - z0) * TEX_M)))
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    zs = z1 - (np.arange(h) + 0.5) / h * (z1 - z0)
    x, z = np.meshgrid(xs, zs)
    # polished black stone in 0.8 m slabs, the bays' joints a brass inlay
    base = stone(x, z, (21, 24, 34), 0.8, seed=int(abs(x0 * 7 + z0 * 3) + 40), grout=0.6, fleck=6)
    rgb = base.copy()
    for k, b in enumerate(BAYS):
        cx = COLS[k]
        m = lit_mask(x, z, [b], soft=0.05)
        # the lamp lights its whole bay, most round its column, softly toward the bay's corners
        d = np.hypot((x - cx) * 0.9, (z - 0.0) * 0.55)
        glow = 0.3 + 0.7 * np.exp(-(d / 1.4) ** 1.5)
        # the column's reflection in the polish, running toward the camera, and a ring of light
        # round the plinth
        refl = np.exp(-((x - cx) / 0.26) ** 2) * smoothstep(-3.6, -0.6, z) * (z < -0.45) * 0.55
        ring = np.exp(-((np.maximum(np.abs(x - cx), np.abs(z)) - 0.58) / 0.12) ** 2) * 0.5
        shimmer = 0.85 + 0.3 * 0.16      # agent W: the net moves (aj_wwater's overlay); the wash keeps its average
        lit = (glow * shimmer + refl + ring) * 0.5          # half strength: the wash is the lamp on
        rgb = rgb + (m * lit)[..., None] * hue(k) * 0.46
    # the bays' joints: thin brass lines across the gallery where one bay meets the next
    for bx in (-6.0, -3.0, 0.0, 3.0, 6.0):
        line = (np.abs(x - bx) < 0.025) & (z < 3.6)
        rgb = np.where(line[..., None], rgb * 0.45 + np.array([46, 40, 26]), rgb)
    # darker where the floor meets the walls
    dd = np.minimum.reduce([x - S.X0, S.X1 - x, z - S.Z0, S.Z1 - z])
    rgb *= (1 - 0.45 * np.exp(-np.clip(dd, 0, None) / 0.2))[..., None]
    return to_image(rgb, 4.0)


def paint_back(w=232, h=40):
    """The back wall's room face from the floor to the top (2.4 m): dark blue-black panels, the
    bays' hues spilling up it faintly over the tank band."""
    x0, x1 = S.X0, S.X1
    xs = x0 + (np.arange(w) + 0.5) / w * (x1 - x0)
    ys = S.H - (np.arange(h) + 0.5) / h * S.H
    x, y = np.meshgrid(xs, ys)
    rgb = np.zeros((h, w, 3)) + np.array([22, 25, 38])
    panel = (np.abs((x / 1.2) % 1 - 0.5) > 0.485)
    rgb = np.where(panel[..., None], rgb * 0.7, rgb)
    for k in range(4):
        cx = COLS[k]
        g = np.exp(-((x - cx) / 1.6) ** 2) * np.exp(-((y - 1.1) / 0.8) ** 2) * 0.35
        rgb += g[..., None] * hue(k) * 0.4
    rgb = np.where((np.abs(y - 1.05) < 0.03)[..., None], np.array([40, 44, 60]), rgb)   # a dado rail
    rgb *= (1 - 0.35 * np.exp(-y / 0.15))[..., None]
    return to_image(rgb, 3.0)


def paint_tanks(w=253, h=26):
    """The wall tanks' band, x -5.5 .. 5.5, from the floor to TANK_Y1: a dark cabinet, then seven
    small tanks in dark frames, each lit in its water's own pale colour, a small life in each."""
    img = Image.new('RGB', (w, h), (18, 20, 28))
    d = ImageDraw.Draw(img)
    n = 7
    pw = w / n
    waters = [(40, 70, 120), (60, 50, 110), (30, 80, 100), (70, 60, 120), (40, 90, 110), (80, 50, 100), (36, 74, 116)]
    rng = np.random.default_rng(5)
    for k in range(n):
        a, b = int(k * pw + 3), int((k + 1) * pw - 3)
        top, bot = 2, h - 7
        water = waters[k]
        for yy in range(top, bot + 1):           # lighter toward the lamp at the top
            t = (yy - top) / (bot - top)
            c = tuple(int(v * (1.25 - 0.55 * t)) for v in water)
            d.line([(a, yy), (b, yy)], fill=c)
        d.line([(a, bot), (b, bot)], fill=(70, 66, 60))       # sand
        d.line([(a, top), (b, top)], fill=tuple(min(255, int(v * 2.2)) for v in water))   # the lamp's line
        life = k % 5
        for _ in range(4 if life != 3 else 6):
            px = int(rng.uniform(a + 3, b - 3))
            py = int(rng.uniform(top + 3, bot - 4))
            if life == 0:          # moon jellies: pale rings
                d.ellipse([px - 2, py - 1, px + 2, py + 1], outline=(200, 210, 240))
            elif life == 1:        # seahorses: pale yellow hooks
                d.line([(px, py - 2), (px, py + 2), (px + 1, py + 3)], fill=(230, 210, 120))
            elif life == 2:        # garden eels: thin pale lines from the sand
                d.line([(px, bot - 1), (px, bot - 5 - rng.integers(0, 4))], fill=(210, 220, 200))
            elif life == 3:        # upside-down jellies on the sand
                d.ellipse([px - 2, bot - 3, px + 2, bot - 1], fill=(120, 140, 110))
            else:                  # anemones: pink tufts
                d.ellipse([px - 2, bot - 3, px + 2, bot], fill=(230, 120, 170))
        d.line([(a + 2, top + 2), (a + 6, top + 2)], fill=(150, 170, 200))   # the glass's glint
    return img


def paint_glass(k, w=8, h=32):
    """A column's water as its glass shows it, side by side quad (fit): the lamp's hue strongest
    at the foot, fading up into the dark, a glint down one edge."""
    t = (np.arange(h) + 0.5) / h                                 # 0 at the top
    rgb = (0.3 + 0.7 * t[:, None, None] ** 1.6) * hue(k)[None, None, :] * np.ones((h, w, 1))
    rgb[:, 1] += 40 * (0.3 + t[:, None] * 0.7)
    return to_image(rgb, 0)


def paint_ripple(n=16):
    """The columns' water surface from above: a soft ripple, 4-bit."""
    i, j = np.meshgrid(np.arange(n), np.arange(n))
    v = np.sin(i * 0.8 + np.sin(j * 0.7) * 1.5) + np.sin(j * 0.9 + np.sin(i * 0.5) * 1.2)
    rgb = np.zeros((n, n, 3)) + 150 + (v[..., None] * 40)
    return to_image(rgb, 0)


# ---- the recipes

def column_nodes(k):
    """A jellyfish column: a low lacquered plinth filling its 1 m square, the round lamp set in its
    top, the glass rising to 2.3 m (its water brightest over the lamp), the lamp's beam inside,
    three jellies and a steel rim round the top."""
    cx = COLS[k]
    g0, g1 = PLINTH_H + 0.03, COL_TOP - 0.05
    n = [box(f'plinth_{k}', (cx - 0.49, -0.02, -0.49), (cx + 0.49, PLINTH_H, 0.49), 'plinth', open=['bottom'],
             faces={'top': 'plinth_top'}),
         at({'id': f'lamp_{k}', 'op': 'cylinder', 'radius': 0.44, 'height': 0.04, 'segments': 12,
             'material': 'rim', 'faces': {'top': f'lamp_{k}'}}, translate=[cx, PLINTH_H + 0.01, 0.0]),
         at({'id': f'glass_{k}', 'op': 'cylinder', 'radius': COL_R, 'height': g1 - g0, 'segments': 12,
             'caps': False, 'material': f'water_{k}'}, translate=[cx, (g0 + g1) / 2, 0.0]),
         at({'id': f'beam_{k}', 'op': 'lathe', 'profile': [[0.38, 0.0], [0.3, 0.6], [0.14, 1.5]], 'segments': 8,
             'caps': False, 'material': f'beam_{k}'}, translate=[cx, g0 + 0.01, 0.0]),
         ring(f'rim_{k}', cx, 0.0, g1, COL_TOP + 0.02, 0.48, 0.41, 12, 'rim')]
    top = Mesh()
    edge = [(cx + 0.43 * math.cos(math.tau * i / 12), g1 - 0.04, 0.43 * math.sin(math.tau * i / 12)) for i in range(12)]
    top.poly(edge, (0, 1, 0), f'surface_{k}')
    n.append(top.node(f'surface_{k}', f'surface_{k}'))
    # the jellies: bells (lathes) in the lamp's pale hue, adding light, and their trailing arms
    arms = Mesh()
    rng = np.random.default_rng(20 + k)
    for j, (dx, y, dz, s) in enumerate(((-0.12, 1.85, 0.1, 1.0), (0.16, 1.45, -0.12, 0.9), (-0.1, 1.05, -0.05, 0.85),
                                         (0.12, 0.65, 0.12, 0.7))):
        dx += rng.uniform(-0.04, 0.04)
        y += rng.uniform(-0.1, 0.1)
        bx, bz = cx + dx, dz
        n.append(at({'id': f'bell_{k}_{j}', 'op': 'lathe', 'profile': [[0.2, 0.0], [0.15, 0.1], [0.0, 0.16]],
                     'segments': 6, 'caps': False, 'material': f'jelly_{k}'},
                    translate=[bx, y, bz], scale=[s, s, s], rotate=[0, j * 25 + k * 10, 0]))
        tl, tw = 0.42 * s, 0.11 * s
        arms.poly([(bx - tw, y + 0.005, bz - 0.1), (bx + tw, y + 0.005, bz - 0.1), (bx + tw * 0.3, y - tl, bz - 0.08),
                   (bx - tw * 0.3, y - tl, bz - 0.08)], (0, 0, -1), f'arm_{k}')
    n.append(arms.node(f'arms_{k}', f'arm_{k}'))
    return n


def tank_nodes():
    x0, z0, x1, z1 = TANKS
    # the band of small tanks set into the back wall over a dark cabinet (both in the texture),
    # inside the tanks' footprint, cut at 1 m
    return [box('wall_tanks', (x0 + 0.01, -0.02, z0 + 0.01), (x1 - 0.01, TANK_Y1, z1 + 0.02), 'tank_frame',
                open=['front', 'bottom'], faces={'back': 'tanks', 'top': 'cut'})]


def room_recipe():
    tiles = S.floor_tiles(3, 2)
    m = {
        'cut': {'color': SECTION_CUT, 'class': 'emissive'},
        'section': mat_tex(P + 'section', '#2e3444', bits=4),
        'end': {'color': '#262c3c'}, 'reveal': {'color': '#2a3040'},
        'door_glow': {'color': '#5a6a80', 'class': 'emissive'},
        'threshold': {'color': '#161a24', 'class': 'emissive'},
        'beyond_wall': {'color': '#141824', 'class': 'emissive'},
        'great_floor': {'color': '#1c3e74', 'class': 'emissive'},
        'great_wall': {'color': '#16284c', 'class': 'emissive'},
        'ocean_floor': {'color': '#2a6c96', 'class': 'emissive'},
        'ocean_wall': {'color': '#1c4064', 'class': 'emissive'},
        'back': mat_tex(P + 'back', '#1c2030'),
        'tanks': mat_tex(P + 'tanks', '#304060'),
        'tank_frame': {'color': '#1a1e28'},
        'plinth': {'color': '#1e2230'}, 'plinth_top': {'color': '#2a2e3c'},
        'rim': {'color': '#5a6278'},
    }
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#20242e')
    for k in range(4):
        m[f'lamp_{k}'] = {'color': hexc(hue(k, 0.95)), 'class': 'emissive'}
        m[f'water_{k}'] = dict(mat_tex(f'{P}glass_{k}', hexc(hue(k, 0.42)), bits=4), blend='half', double_sided=True)
        m[f'beam_{k}'] = {'color': hexc(hue(k, 0.5)), 'class': 'emissive', 'blend': 'quarter'}
        m[f'surface_{k}'] = {'color': hexc(hue(k, 0.6)), 'class': 'emissive', 'blend': 'quarter',     # agent W: it moves
                             'texture': wateranim.texture(WATER_RIPPLE)}
        m[f'jelly_{k}'] = {'color': hexc(hue(k, 0.45) + 45), 'class': 'emissive', 'blend': 'add', 'smooth': True}
        m[f'arm_{k}'] = {'color': hexc(hue(k, 0.3) + 40), 'class': 'emissive', 'blend': 'add', 'double_sided': True}
    n = [S.floor_mesh(tiles), S.front_wall(), S.end_wall('w'), S.end_wall('e')]
    n.append(S.back_wall([(0.0, S.H, [(S.X0, S.X1, 'back')])]))
    n.append(S.beyond('great', 1.6, far='great_floor', wall='great_wall'))
    n.append(S.beyond('ocean', 1.6, far='ocean_floor', wall='ocean_wall'))
    n += tank_nodes()
    cols = [c for k in range(4) for c in column_nodes(k)]
    lighting = {'direction': [-0.3, 0.8, -0.5], 'ambient': 0.35, 'diffuse': 0.3}
    # two recipes: the shell (the World Kit's stand-in for the cell is made from it: under 700
    # triangles) and the four columns
    return [recipe(P + 'room', m, n, lighting, 700), recipe(P + 'columns', m, cols, lighting, 1400)]


# ---- agent W: the moving water (NOTES_W.md)

WATER_RIPPLE = wateranim.key('w_ripple', '#f0f0ff', base='#707080')


def wwater_recipe():
    """The light through each column's water, a caustic net on the floor round its plinth in the
    bay's hue, lit by a light of its own in the column."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('net', 'w_caustic')
    for k, (x0, z0, x1, z1) in enumerate(BAYS):
        ov.floor('net', 0.03, x0 + 0.03, x1 - 0.03, max(z0, -2.2), min(z1, 2.2), nx=2, nz=2)
        ov.light((COLS[k], 0.9, 0.0), HUES[k], 0.9, 2.0, id=f'column_{k}')
    return ov.recipe(ART, refine={'tolerance': 20, 'max_added': 48})


def main():
    art = {}
    for name, x0, x1, z0, z1 in S.floor_tiles(3, 2):
        art[P + name] = paint_floor_tile(x0, x1, z0, z1)
    art[P + 'back'] = paint_back()
    art[P + 'tanks'] = paint_tanks()
    keys = list(art)
    for k, img in zip(keys, quantise_together([art[k] for k in keys])):
        art[k] = img
    art[P + 'section'] = paint_section(S.XO0, S.XO1)
    art[P + 'ripple'] = paint_ripple()
    for k in range(4):
        art[f'{P}glass_{k}'] = paint_glass(k)
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    recs = room_recipe()
    for rec in recs:
        wateranim.finish(rec, ART)          # agent W: the columns' ripple tile (in the materials both share)
    for rec in recs + [wwater_recipe(), collision(G.ROOM, P + 'room_col')]:     # agent W: wwater
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'columns', 'asset': P + 'columns', 'position': [0, 0, 0], 'collision': 'none'},
                  {'id': P + 'wwater', 'asset': P + 'wwater', 'position': [0, 0, 0], 'collision': 'none'}]  # agent W
    data = {'format': 'after-hours-placements', 'version': 1, 'room': 'aq_jelly', 'placements': placements}
    write_json(HERE / 'aq_jelly.placements.json' if '--placements' in sys.argv else OUT / 'draft.placements.json', data)


if __name__ == '__main__':
    main()
