#!/usr/bin/env python3
"""The aquarium, room 1: the great tank, dressed. Writes the room's Asset Kit recipes into dressed/,
their textures into dressed/art/ and aq_great.placements.json beside this script.

    python3 carts/afterhours/rooms/aq_great/dress_aq_great.py

The cathedral of the building, on two levels:

- below, the long dark gallery: a dark terrazzo floor, its only light the blue band the window
  throws on it (painted, caustics and all, exactly over the play file's light box), two low
  benches facing the glass, the column;
- the window: one acrylic wall the whole width, floor to catwalk, in a steel frame with its
  panels' seams; behind it the great tank: sand in the light from above, rock, kelp, a sardine
  school wheeling by the glass, groupers, an eagle ray low down, a manta near the surface, light
  coming down through the water (the glass's glow, strongest at its head);
- above (+3.2 m), the keepers' catwalks over the tank's open water: the rim along the tank's front
  edge, grated and railed, with its two clamp lamps (their pools painted on the grating exactly
  over the light boxes), two bridges and the feeding platform with its hopper, the solid walk
  along the back, and the back wall above the water with the tank's ripples on it and the
  keepers' hoses, net and gauges.

From the surface the water is dark, its ripples and the lamps' glints on it (half-blended over
the tank), so that it reads as water and not as a second window: the window is the bright face
seen from below, the surface the dark one seen from above.

The floor plan is the level lead's (PLAN.md, make_aq_great.py), imported for its numbers only.
Needs NumPy and Pillow.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOMS = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOMS / 'corridor'))
sys.path.insert(0, str(ROOMS / 'arrival'))
sys.path.insert(0, str(ROOMS.parent / 'levels' / 'aquarium'))
import make_aq_great as G  # noqa: E402  (the lead's plan: imported for its numbers only)
import aqroom  # noqa: E402
import s2room  # noqa: E402
from dresskit import (Mesh, at, blob, box, grid, hex_rgb, recipe, rect, save_png, smoothstep, to_image,  # noqa: E402
                      write_json)
from s2dress import paint_section  # noqa: E402
sys.path.insert(0, str(ROOMS.parent / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'ag_'
D = G.ROOM
X0, X1 = G.X
Z0, Z1 = G.Z
U = G.UPPER
T = 0.25
XO0, XO1, ZO0, ZO1 = X0 - T, X1 + T, Z0 - T, Z1 + T
H = U + 2.4                     # the back and end walls' tops
SLAB = 0.4
CUT_H = 1.0
WIN_Z0, WIN_Z1 = G.WINDOW[1], G.WINDOW[3]
RIM_Z0, RIM_Z1 = G.RIM[1], G.RIM[3]
BACK_Z0 = G.BACK[1]
DECK = 0.15                     # the catwalks' deck thickness
SAND_Y = 0.25                   # the tank's sand
WATER_Y = 2.95                  # the tank's surface, 0.25 m under the catwalks
GLASS_TOP = 3.0
PROPS = {p[0]: p for p in D['props']}
UPROPS = {p[0]: p for p in D['upper_props']}
LIGHTS = {L[0]: L for L in D['lights']}
BAND = LIGHTS['window'][1]
RIM_LIGHTS = [LIGHTS['rim_w'][1], LIGHTS['rim_m'][1]]
LAMPS = [(-7.6, 'rim_w'), (-1.55, 'rim_m'), (1.55, 'rim_m')]      # clamp lamps on the rim's back rail
GAPS0 = {s: sorted(dr['at'] for dr in D['doors'] if dr['side'] == s and dr.get('level', 0) == 0) for s in 'we'}
GAPS1 = {s: sorted(dr['at'] for dr in D['doors'] if dr['side'] == s and dr.get('level', 0) == 1) for s in 'we'}
SEAMS = (-5.0, 0.0, 5.0)        # the acrylic panels' seams
PIER = 0.35


# ---- painting helpers

def caustics(x, z, scale=1.0, seed=0.0):
    """A caustic net: bright thin lines, 0..1 (the aquarium sketch's)."""
    x = x * scale
    z = z * scale
    a = np.sin(x * 2.1 + np.sin(z * 1.7 + seed) * 1.4 + seed)
    b = np.sin(z * 2.6 + np.sin(x * 1.3 - seed) * 1.2 - seed * 0.5)
    c = np.sin((x + z) * 1.6 + np.sin((x - z) * 1.1 + seed) * 1.1)
    v = (a + b + c) / 3.0
    return np.clip(1 - np.abs(v) * 2.6, 0, 1) ** 3


def rbox_sdf(x, z, b, rad):
    """Signed distance to a box (x0, z0, x1, z1) with its corners rounded by rad: < 0 inside."""
    x0, z0, x1, z1 = b
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    hx, hz = (x1 - x0) / 2 - rad, (z1 - z0) / 2 - rad
    qx, qz = np.abs(x - cx) - hx, np.abs(z - cz) - hz
    return np.hypot(np.clip(qx, 0, None), np.clip(qz, 0, None)) + np.minimum(np.maximum(qx, qz), 0) - rad


def pool(x, z, b, rad=0.3, fade=0.18, edge=0.45):
    """A light box's pool: full a little inside the box, `edge` on its edge, nothing 4 cm out.
    What looks lit is the box, its corners rounded."""
    d = rbox_sdf(x, z, b, rad)
    inside = edge + (1 - edge) * smoothstep(0.0, fade, -d)
    return np.where(d <= 0, inside, edge * (1 - smoothstep(0.0, 0.04, d)))


def emissive(color, image=None, bits=8, **tex):
    m = {'color': color, 'class': 'emissive'}
    if image:
        m['texture'] = {'image': f'art/{image}.png', 'bits': bits, 'projection': 'fit', **tex}
    return m


def textured(color, image, bits=4, **extra):
    m = {'color': color, 'texture': {'image': f'art/{image}.png', 'bits': bits, 'projection': 'fit'}}
    m.update(extra)
    return m


# ---- the gallery's floor

def floor_tiles():
    return [(f'floor_{i}', a, b) for i, (a, b) in enumerate(((X0, 0.0), (0.0, X1)))]


def paint_floor(x0, x1, w=255, h=127):
    x, z = grid(x0, x1, Z0, WIN_Z0, w, h)
    rng = np.random.default_rng(abs(int(x0 * 10)) + 31)
    # dark terrazzo: blue-black with pale chips, brass strips every 1.5 m
    base = np.zeros((h, w, 3)) + np.array([44, 54, 76])
    chips = rng.random((h, w))
    base += (chips > 0.94)[..., None] * np.array([36, 40, 46])
    base += (chips < 0.05)[..., None] * np.array([-14, -16, -20])
    strip = (np.abs(((x + 0.75) / 1.5) % 1 - 0.5) > 0.485) | (np.abs(((z + 0.25) / 1.5) % 1 - 0.5) > 0.485)
    base = np.where(strip[..., None], np.array([70, 66, 54]), base)
    # a dark runner where the visitors stand before the glass, and mats at the doors
    for (a, b) in GAPS0['w']:
        base = np.where((rect(x, z, X0, a + 0.05, X0 + 0.9, b - 0.05) > 0)[..., None], base * 0.45, base)
    for (a, b) in GAPS0['e']:
        base = np.where((rect(x, z, X1 - 0.9, a + 0.05, X1, b - 0.05) > 0)[..., None], base * 0.45, base)
    # the room is dark: a faint cool ambient, darker toward the front and the walls
    amb = 0.32 + 0.08 * smoothstep(Z0, BAND[1], z)
    shade = np.zeros((h, w, 3)) + amb[..., None]
    # the window's light, only on its box: strongest at the glass, caustics through it
    lit = pool(x, z, BAND, rad=0.06, fade=0.22, edge=0.55)
    near = np.exp(-(WIN_Z0 - z) / 1.1)
    caus = 0.13                 # agent W: the net moves (ag_wwater's overlay); the floor keeps its average, a little under
    glow = (0.9 + 1.5 * near + 2.2 * caus * (0.35 + near)) * lit
    shade += glow[..., None] * np.array([0.32, 0.72, 1.05])
    rgb = base * shade
    # the slot of light along the sill, and the window seams' and piers' faint shadows in it
    rgb += (np.exp(-((WIN_Z0 - z) / 0.25) ** 2) * lit)[..., None] * np.array([30, 90, 140])
    for sx in SEAMS:
        sh = np.exp(-((x - sx - (WIN_Z0 - z) * 0.15) / 0.05) ** 2) * lit * 0.35
        rgb *= (1 - sh)[..., None]
    for px in (X0 + PIER / 2, X1 - PIER / 2):
        rgb *= (1 - 0.5 * np.exp(-((x - px) / 0.4) ** 2) * lit)[..., None]
    # the benches' feet and the column catch a little of the glow, toward the camera: no light
    # beyond the box; the benches' soft dark footprints
    for pid in ('bench_w', 'bench_e', 'column'):
        bx0, bz0, bx1, bz1 = PROPS[pid][2]
        rgb *= (1 - 0.35 * rect(x, z, bx0 - 0.08, bz0 - 0.1, bx1 + 0.08, bz1 + 0.04, soft=0.08))[..., None]
    return to_image(rgb)


# ---- the back wall over the water, and the walk along it

def paint_back(x0, x1, w=255, h=60):
    x, y = grid(x0, x1, U, H, w, h)
    rng = np.random.default_rng(abs(int(x0)) + 50)
    base = np.zeros((h, w, 3)) + np.array([66, 74, 86]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    # board-marked concrete in panels 2.5 m wide with tie holes
    joint = np.abs(((x + 1.25) / 2.5) % 1 - 0.5) > 0.49
    base *= np.where(joint, 0.75, 1.0)[..., None]
    for ty in (U + 0.6, U + 1.5):
        ties = (np.abs(((x + 0.625) / 1.25) % 1 - 0.5) < 0.02) & (np.abs(y - ty) < 0.03)
        base = np.where(ties[..., None], base * 0.6, base)
    # the tank's ripples thrown up on the wall by the water's light, strongest low down
    caus = 0.12                 # agent W: the ripples' light moves (ag_wwater's overlay)
    low = np.exp(-(y - U) / 1.0)
    rgb = base * (0.5 + 0.15 * low)[..., None]
    rgb += (caus * low * 0.6)[..., None] * np.array([20, 56, 76])
    # a water main along the wall at 1.9 m, with valves; a smaller pipe under it
    for py, r_, col in ((U + 1.95, 0.07, (70, 84, 96)), (U + 1.6, 0.035, (90, 70, 60))):
        p = np.abs(y - py) < r_
        rgb = np.where(p[..., None], np.array(col) * (1.1 - 0.4 * ((y - py) / r_ + 1) / 2)[..., None], rgb)
    for vx in (-7.0, -2.5, 3.5, 8.0):
        rgb = np.where((rect(x, y, vx - 0.08, U + 1.8, vx + 0.08, U + 2.1) > 0)[..., None], np.array([150, 40, 36]), rgb)
    return to_image(rgb, 4.0)


def draw_gear(img, x0, x1):
    """The keepers' gear hung on the back wall: hoses coiled on hooks, long-handled nets, a life
    ring, a depth gauge, a hook board (shapes only, no words)."""
    w, h = img.size
    d = ImageDraw.Draw(img)

    def px(x, y):
        return ((x - x0) / (x1 - x0) * w, (H - y) / (H - U) * h)
    for hx in (-8.6, 2.6, 6.8):                       # hoses on hooks
        if x0 <= hx <= x1:
            cx, cy = px(hx, U + 1.1)
            for k, rr in enumerate((7, 6, 5)):
                d.ellipse([cx - rr * 1.2, cy - rr, cx + rr * 1.2, cy + rr], outline=(46, 120, 74) if k % 2 else (36, 98, 60))
            d.line([px(hx, U + 0.55), px(hx + 0.2, U + 0.1)], fill=(36, 98, 60))
    for nx in (-4.2, 5.4):                            # nets, leaning, handles to the deck
        if x0 <= nx <= x1:
            a, b = px(nx, U + 0.05), px(nx + 0.5, U + 2.0)
            d.line([a, b], fill=(160, 150, 120))
            cx, cy = b
            d.ellipse([cx - 5, cy - 7, cx + 5, cy + 3], outline=(140, 150, 150))
            for k in range(-3, 4, 2):
                d.line([(cx + k, cy - 6), (cx + k, cy + 2)], fill=(90, 100, 104))
    if x0 <= -0.4 <= x1:                              # a life ring by the feed station
        cx, cy = px(-0.4, U + 1.25)
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], outline=(220, 110, 50), width=3)
        for k in range(4):
            a = k * math.pi / 2 + 0.4
            d.line([(cx + 4 * math.cos(a), cy + 4 * math.sin(a)), (cx + 6 * math.cos(a), cy + 6 * math.sin(a))],
                   fill=(230, 230, 220), width=2)
    if x0 <= 0.9 <= x1:                               # a depth gauge and a hook board
        cx, cy = px(0.9, U + 1.35)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(200, 204, 196), outline=(40, 44, 50))
        d.line([(cx, cy), (cx + 2, cy - 3)], fill=(180, 40, 30))
        bx0, by0 = px(1.4, U + 1.55)
        bx1, by1 = px(2.0, U + 1.05)
        d.rectangle([bx0, by0, bx1, by1], fill=(70, 80, 66))
        for k in range(4):
            d.line([(bx0 + 3 + k * 4, by0 + 3), (bx0 + 3 + k * 4, by0 + 7)], fill=(190, 190, 170))
    return img


def paint_backwalk(x0, x1, w=255, h=32):
    """The walk along the tank's back: concrete coping, a yellow edge line at the water, the keepers'
    feed buckets and a coiled hose by the wall. Unlit: the keeper's torch is its light."""
    x, z = grid(x0, x1, BACK_Z0, ZO1, w, h)
    rng = np.random.default_rng(abs(int(x0)) + 7)
    base = np.zeros((h, w, 3)) + np.array([62, 70, 80]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    base *= np.where(np.abs(((x + 1.0) / 2.0) % 1 - 0.5) > 0.49, 0.75, 1.0)[..., None]
    base = np.where((np.abs(z - BACK_Z0 - 0.06) < 0.04)[..., None], np.array([150, 130, 50]), base)
    # wet patches by the edge
    base *= (1 - 0.25 * smoothstep(0.4, 0.0, z - BACK_Z0) * (np.sin(x * 1.7) * 0.5 + 0.5))[..., None]
    rgb = base * 0.45
    for bx in (-2.1, -1.75, 3.9):                     # feed buckets by the wall
        dd = np.hypot(x - bx, z - 4.88)
        rgb = np.where((dd < 0.13)[..., None], np.array([60, 90, 140]) * 0.6, rgb)
        rgb = np.where((dd < 0.09)[..., None], np.array([70, 50, 34]) * 0.8, rgb)
    hx, hz = 7.6, 4.8                                 # a hose coiled on the deck by the wall
    dd = np.hypot(x - hx, (z - hz) * 1.6)
    ring = (np.abs((dd % 0.07) - 0.035) < 0.015) & (dd < 0.28)
    rgb = np.where(ring[..., None], np.array([30, 80, 50]), rgb)
    return to_image(rgb, 4.0)


# ---- the catwalks' grating, with the lamps' pools

def grate_holes(x, z, along='x'):
    """Slots in the grating: bearing bars every 3 texels, cross bars every 4 (what a grate is at
    24 px a metre: a darker, finer tone with the water through it)."""
    h, w = x.shape
    i, j = np.meshgrid(np.arange(w), np.arange(h))
    if along == 'x':
        return (j % 3 == 1) & (i % 4 != 0)
    return (i % 3 == 1) & (j % 4 != 0)


def paint_grate(x0, x1, z0, z1, w, h, lights=(), along='x', rim_edge=False):
    x, z = grid(x0, x1, z0, z1, w, h)
    rng = np.random.default_rng(abs(int((x0 + z0) * 10)) + 3)
    base = np.zeros((h, w, 3)) + np.array([92, 100, 112]) + (rng.random((h, w)) - 0.5)[..., None] * 12
    shade = np.zeros((h, w, 3)) + 0.55
    for b in lights:
        lit = pool(x, z, b, rad=0.3, fade=0.25, edge=0.5)
        # the lamp's own hot spot near its rail
        lx = (b[0] + b[2]) / 2
        hot = 0.8 + 0.5 * np.exp(-((x - lx) / max(0.8, (b[2] - b[0]) / 2.5)) ** 2 - ((z - b[3]) / 0.9) ** 2)
        shade += (lit * hot * 2.3)[..., None] * np.array([1.0, 0.86, 0.6])
    rgb = base * shade
    if rim_edge:     # a yellow kick line along the rim's front edge, over the gallery
        rgb = np.where((np.abs(z - RIM_Z0 - 0.05) < 0.035)[..., None], rgb * np.array([1.5, 1.3, 0.45]), rgb)
    img = to_image(rgb, 3.0).convert('RGBA')
    a = np.where(grate_holes(x, z, along), 0, 255).astype(np.uint8)
    img.putalpha(Image.fromarray(a, 'L'))
    return img


def paint_rail(n=16):
    """A railing bay a metre long: a post, the top rail, a knee rail and a toe board; the rest
    holes."""
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (178, 186, 196, 255)
    d.line([(0, 0), (n, 0)], fill=c)
    d.line([(0, 8), (n, 8)], fill=c)
    d.rectangle([0, 14, n, 15], fill=(150, 156, 166, 255))
    d.line([(0, 0), (0, n)], fill=c)
    return img


# ---- the tank: sand, its back, the water from above, the glass, kelp

def paint_sand(x0, x1, w=200, h=54):
    x, z = grid(x0, x1, RIM_Z0, BACK_Z0, w, h)
    rng = np.random.default_rng(abs(int(x0)) + 11)
    rgb = np.zeros((h, w, 3)) + np.array([40, 82, 112]) + (rng.random((h, w)) - 0.5)[..., None] * np.array([14, 16, 18])
    ripple = np.sin(x * 9 + np.sin(z * 4) * 1.5) * 0.5 + 0.5
    rgb += (ripple * 0.15)[..., None] * np.array([24, 32, 34])
    rgb += 0.13 * np.array([34, 70, 80])      # agent W: the net moves (ag_wwater's overlay)
    # the far sand fades into the water's blue: what the window shows high up is far off
    far = smoothstep(RIM_Z0, RIM_Z0 + 1.8, z)[..., None]
    rgb = rgb * (1 - 0.6 * far) + np.array([14, 40, 78]) * 0.6 * far
    # the rocks' and the kelp's shade on the sand
    for (rx, rz, rs) in ROCKS:
        rgb *= (1 - 0.45 * blob(x, z, rx + 0.1, rz + 0.1, rs[0] * 1.2, rs[2] * 1.2))[..., None]
    return to_image(rgb, 5.0)


def paint_tank_back(w=255, h=40):
    """The tank's back wall under the back walk, as the water from above shows it: deep blue,
    the rock work dark along its foot, ripples of light on it near the top."""
    x, y = grid(X0, X1, 0.2, 3.05, w, h)
    depth = np.clip((WATER_Y - y) / (WATER_Y - SAND_Y), 0, 1)
    top = np.array([22, 60, 96])
    bottom = np.array([4, 14, 34])
    rgb = top * (1 - depth[..., None]) ** 1.4 + bottom * (1 - (1 - depth[..., None]) ** 1.4)
    rgb += (caustics(x, y * 2, 1.4, 0.9) * (1 - depth) ** 1.5)[..., None] * np.array([14, 36, 44])
    ridge = SAND_Y + 0.5 + 0.3 * np.sin(x * 0.9) + 0.2 * np.sin(x * 2.7 + 1) + 0.1 * np.sin(x * 6.1)
    rgb = np.where((y < ridge)[..., None], rgb * 0.5 + np.array([6, 12, 24]), rgb)
    rgb = np.where((y > WATER_Y)[..., None], np.array([16, 26, 40]), rgb)
    return to_image(rgb, 4.0)


def paint_water(x0, x1, w=128, h=68):
    """The surface seen from above, half-blended over the tank: dark navy, ripples catching the
    tank's light, the clamp lamps' warm glints near the rim. 4 bits."""
    x, z = grid(x0, x1, RIM_Z0, BACK_Z0, w, h)
    v = (np.sin(x * 5.0 + np.sin(z * 4.0) * 0.8) + np.sin(z * 6.0 + np.sin(x * 3.1) * 1.2 + 1)
         + np.sin((x + z) * 4.4 + 2)) / 3
    c = np.full_like(v, 0.2)    # agent W: the ripples and glints move (ag_wwater's overlay): their average here
    rgb = np.array([2, 10, 22]) + c[..., None] * np.array([34, 74, 100])
    for lx, lid in LAMPS:
        g = np.exp(-((x - lx) / 0.9) ** 2 - ((z - (RIM_Z1 + 0.25)) / 0.45) ** 2)
        rgb += (g * (0.35 + 1.4 * c))[..., None] * np.array([150, 120, 70])
    return to_image(rgb, 3.0)


def paint_glass(w=8, h=32):
    """The window's glow, added over the tank: stronger at the top, where the light comes in."""
    y = (np.arange(h) + 0.5) / h
    col = np.array([18, 62, 110])[None, :] * (1.3 - 0.95 * y[:, None]) + np.array([4, 10, 18])
    rgb = np.repeat(col[:, None, :], w, axis=1)
    return to_image(rgb, 0)


def paint_kelp(w=16, h=64):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for yy in range(h):
        cx = w / 2 + math.sin(yy / 8.0) * 3.0
        half = 2.0 + 1.6 * math.sin(yy / 5.0 + 1) ** 2
        s = 0.5 + 0.5 * (1 - yy / h)
        d.line([(cx - half, yy), (cx + half, yy)], fill=(int(46 * s), int(120 * s), int(96 * s), 255))
        if yy % 7 == 3:
            d.point((cx + half + 1, yy), fill=(110, 170, 120, 255))
    return img


def paint_feed(n=16):
    """The hopper's contents where the section cuts it: feed pellets."""
    rng = np.random.default_rng(5)
    rgb = np.zeros((n, n, 3)) + np.array([110, 80, 50]) + (rng.random((n, n, 1)) - 0.5) * 40
    return to_image(rgb, 0)


# ---- the room's shell and its catwalks

ROCKS = [(-9.2, 1.75, (0.6, 0.55, 0.45)), (-8.4, 1.6, (0.35, 0.3, 0.3)), (8.9, 1.7, (0.7, 0.6, 0.45)),
         (-6.8, 3.7, (0.8, 0.9, 0.35)), (-1.8, 3.75, (0.6, 0.6, 0.3)), (2.6, 3.7, (0.9, 1.0, 0.35)),
         (7.4, 3.75, (0.6, 0.7, 0.3))]


def end_wall_nodes():
    n = []
    for s in 'we':
        ax0, ax1 = (XO0, X0) if s == 'w' else (X1, XO1)
        inner, outer = ('right', 'left') if s == 'w' else ('left', 'right')
        for lvl, gaps, y0, y1 in ((0, GAPS0[s], -SLAB, 2.1), (1, GAPS1[s], U, H)):
            for i, (a, b) in enumerate(s2room.segments(ZO0, ZO1, gaps)):
                op = ['bottom', outer] + (['top'] if lvl == 0 else [])
                faces = {inner: 'end_in', 'back': 'cut' if a == ZO0 else 'reveal'}
                if b >= ZO1:
                    op.append('front')
                else:
                    faces['front'] = 'reveal'
                if lvl == 1:
                    faces['top'] = 'cut'
                n.append(box(f'end_{s}{lvl}_{i}', (ax0, y0, a), (ax1, y1, b), 'end_in', open=op, faces=faces))
            if lvl == 1:
                for i, (a, b) in enumerate(gaps):
                    n.append(box(f'end_{s}_lintel_{i}', (ax0, U + 2.1, a), (ax1, H, b), 'end_in',
                                 open=['front', 'back', outer], faces={'bottom': 'soffit', 'top': 'cut', inner: 'end_in'}))
        # the band between the levels: its underside is the floor doorway's head, its top the upper
        # doorway's sill
        n.append(box(f'end_{s}_band', (ax0, 2.1, ZO0), (ax1, U, ZO1), 'end_in', open=[outer, 'front'],
                     faces={'bottom': 'soffit', 'top': 'threshold', 'back': 'cut', inner: 'end_in'}))
        for i, (a, b) in enumerate(GAPS0[s]):
            n.append(box(f'end_{s}_sill_{i}', (ax0, -SLAB, a), (ax1, 0.0, b), 'cut',
                         open=['bottom', 'front', 'back', inner, outer], faces={'top': 'threshold'}))
    return n


def beyond_nodes():
    """The ways on beyond the doorways: the corridor to the entrance hall and the jellyfish
    gallery's violet at the floor, the mezzanine's landing and the stair up to the tank tops."""
    m = Mesh()
    for dr in D['doors']:
        a, b = dr['at']
        lvl = dr.get('level', 0)
        y = U if lvl else 0.0
        s = 1 if dr['side'] == 'e' else -1
        xw = XO1 if s > 0 else XO0
        L = 1.4
        mat = {'jelly': 'beyond_jelly', 'hall': 'beyond_hall', 'tops': 'beyond_tops', 'hall_up': 'beyond_hall'}[dr['id']]
        lo, hi = sorted((xw, xw + s * L))
        m.quad_y(y, lo, hi, a, b, 1, mat)
        steps = 4 if dr['id'] == 'tops' else 0
        rise, run = 0.2, 0.28
        for k in range(steps):
            x0 = xw + s * (L + k * run)
            x1 = x0 + s * run
            m.quad_x(x0, y + k * rise, y + (k + 1) * rise, a, b, -s, 'riser')
            m.quad_y(y + (k + 1) * rise, *sorted((x0, x1)), a, b, 1, mat)
        far = xw + s * (L + steps * run)
        for z, f in ((a, 1), (b, -1)):
            m.quad_z(z, *sorted((xw, far)), y - 0.02, y + 2.1 + steps * rise, f, 'beyond_wall')
    return [m.node('beyond', 'beyond_wall')]


def shell_nodes():
    n = []
    for name, a, b in floor_tiles():
        n.append(box(name, (a, -0.05, Z0), (b, 0.0, WIN_Z0), name, open=['bottom', 'left', 'right', 'back', 'front']))
    m = Mesh()
    m.prism([(X0, -SLAB), (X1, -SLAB), (X1, CUT_H), (X0, CUT_H)], ZO0, Z0, 'cut', back='section',
            sides={0: None, 1: None, 3: None})
    n.append(m.node('front_wall', 'cut'))
    n += end_wall_nodes()
    # the back wall over the back walk, in two textured chunks
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        n.append(box(f'back_{k}', (a, U, Z1), (b, H, ZO1), 'end_in', open=['bottom', 'left', 'right', 'front'],
                     faces={'back': f'back_{k}', 'top': 'cut'}))
    n += beyond_nodes()
    return n


def window_nodes():
    """The window's frame (the glass is the tank's): the sill, the piers, the head under the rim and
    the panels' seams."""
    n = [box('sill', (X0, -0.02, WIN_Z0), (X1, 0.3, WIN_Z1), 'frame', open=['bottom', 'front', 'left', 'right'],
             faces={'top': 'sill_top'}),
         box('head', (X0, GLASS_TOP, WIN_Z0 - 0.02), (X1, U - 0.1, WIN_Z1), 'frame',
             open=['bottom', 'front', 'left', 'right'], faces={'top': 'frame_top'})]
    for s in (-1, 1):
        xa, xb = (X0, X0 + PIER) if s < 0 else (X1 - PIER, X1)
        n.append(box(f'pier_{"we"[s > 0]}', (xa, 0.3, WIN_Z0 - 0.04), (xb, GLASS_TOP, WIN_Z1), 'frame',
                     open=['bottom', 'top', 'front', 'left' if s < 0 else 'right']))
    for k, sx in enumerate(SEAMS):
        n.append(box(f'seam_{k}', (sx - 0.025, 0.3, WIN_Z0 - 0.01), (sx + 0.025, GLASS_TOP, WIN_Z0 + 0.06), 'seam',
                     open=['bottom', 'top', 'front']))
    return n


def catwalk_nodes():
    n = []
    y0 = U - DECK
    # the rim: four grated chunks over the window and the water
    for k in range(4):
        a, b = X0 + 5 * k, X0 + 5 * (k + 1)
        n.append(box(f'rim_{k}', (a, y0, RIM_Z0), (b, U, RIM_Z1), 'deck_edge', open=['bottom', 'front', 'left', 'right'],
                     faces={'top': f'rim_{k}', 'back': 'deck_edge'}))
    # the bridges and the feeding platform, grated, out over the water
    for k, (a, za, b, zb) in enumerate(G.BRIDGES):
        n.append(box(f'bridge_{k}', (a, y0, za), (b, U, zb), 'deck_edge', open=['bottom', 'back', 'front'],
                     faces={'top': 'bridge'}))
    fa, fza, fb, fzb = G.FEED
    n.append(box('feed', (fa, y0, fza), (fb, U, fzb), 'deck_edge', open=['bottom', 'back'], faces={'top': 'feed_deck'}))
    # the walk along the back: solid, over the tank's back wall
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        n.append(box(f'backwalk_{k}', (a, y0, BACK_Z0), (b, U, ZO1), 'deck_edge',
                     open=['bottom', 'left', 'right', 'front'], faces={'top': f'backwalk_{k}'}))
    # the railings: one cutout quad a run, a metre a bay, 1 m high
    runs_x = [(RIM_Z0, X0 + 0.01, X1 - 0.01)]
    rb = sorted([X0 + 0.01, X1 - 0.01] + [v for q in G.BRIDGES for v in (q[0], q[2])] + [fa, fb])
    runs_x += [(RIM_Z1, rb[i], rb[i + 1]) for i in range(0, len(rb), 2)]
    bb = sorted([X0 + 0.01, X1 - 0.01] + [v for q in G.BRIDGES for v in (q[0], q[2])])
    runs_x += [(BACK_Z0, bb[i], bb[i + 1]) for i in range(0, len(bb), 2)]
    runs_x.append((fzb, fa, fb))
    runs_z = [(q[0], q[1], q[3]) for q in G.BRIDGES] + [(q[2], q[1], q[3]) for q in G.BRIDGES]
    runs_z += [(fa, fza, fzb), (fb, fza, fzb)]
    rm = Mesh()
    for z, a, b in runs_x:
        rm.quad_z(z, a, b, 0.0, CUT_H, -1, 'rail')
    for x, a, b in runs_z:
        rm.quad_x(x, 0.0, CUT_H, a, b, -1, 'rail')
    node = rm.node('rails', 'rail')
    node['transform'] = {'translate': [0, U, 0]}
    n.append(node)
    # the feed hopper on the platform (it blocks): a stand, the bin cut by the section, a chute
    hx0, hz0, hx1, hz1 = UPROPS['hopper'][2]
    n.append(box('hopper_stand', (hx0 + 0.04, U - 0.02, hz0 + 0.04), (hx1 - 0.04, U + 0.55, hz1 - 0.04), 'hopper',
                 open=['bottom', 'top']))
    n.append(at({'id': 'hopper_bin', 'op': 'lathe', 'profile': [[0.14, 0.0], [0.41, 0.42]], 'segments': 4,
                 'material': 'hopper_bin', 'faces': {'top': 'feed_top'}},
                translate=[(hx0 + hx1) / 2, U + 0.56, (hz0 + hz1) / 2], rotate=[0, 45, 0]))
    cm = Mesh()
    cm.poly([(hx0 + 0.2, U + 0.62, hz1), (hx1 - 0.2, U + 0.62, hz1), (hx1 - 0.2, U + 0.45, hz1 + 0.35),
             (hx0 + 0.2, U + 0.45, hz1 + 0.35)], (0, 1, 0.3), 'hopper')
    n.append(cm.node('chute', 'hopper'))
    # the clamp lamps on the rim's back rail, their lenses toward the rim
    for k, (lx, _) in enumerate(LAMPS):
        n.append(box(f'lamp_{k}', (lx - 0.11, U + 0.84, RIM_Z1 - 0.2), (lx + 0.11, U + 0.98, RIM_Z1 + 0.04), 'lamp',
                     faces={'back': 'lens', 'bottom': 'lens'}))
    return n


def gallery_nodes():
    n = []
    for pid in ('bench_w', 'bench_e'):
        x0, z0, x1, z1 = PROPS[pid][2]
        top = PROPS[pid][3]
        n.append(box(f'{pid}_seat', (x0, top - 0.1, z0), (x1, top, z1), 'bench', open=['bottom'], faces={'top': 'bench_top'}))
        for j, fx in enumerate((x0 + 0.35, x1 - 0.55)):
            n.append(box(f'{pid}_foot_{j}', (fx, -0.02, z0 + 0.1), (fx + 0.2, top - 0.1, z1 - 0.1), 'bench_foot',
                         open=['bottom', 'top']))
    x0, z0, x1, z1 = PROPS['column'][2]
    n.append(box('column', (x0, 0.1, z0), (x1, CUT_H, z1), 'column', open=['bottom'], faces={'top': 'cut'}))
    # a skirting band round the column, catching the blue
    n.append(box('column_base', (x0 - 0.03, -0.02, z0 - 0.03), (x1 + 0.03, 0.12, z1 + 0.03), 'column_base',
                 open=['bottom']))
    return n


def room_lights():
    out = [{'id': f'window_{k}', 'at': [x, 1.4, 0.5], 'color': '#3aa4f0', 'intensity': 0.9, 'range': 4.0}
           for k, x in enumerate((-7.5, -2.5, 2.5, 7.5))]
    out += [{'id': f'lamp_{k}', 'at': [lx, U + 0.85, RIM_Z1 - 0.5], 'color': '#ffe0a8', 'intensity': 1.4, 'range': 2.4}
            for k, (lx, _) in enumerate(LAMPS)]
    return out


def room_recipe():
    m = {
        'cut': {'color': '#3c475e', 'class': 'emissive'},
        'section': {'color': '#4a5468', 'class': 'emissive',
                    'texture': {'image': f'art/{P}section.png', 'bits': 4, 'projection': 'fit'}},
        'end_in': {'color': '#26324a'}, 'reveal': {'color': '#2c3850'},
        'soffit': {'color': '#34486a', 'class': 'emissive'}, 'threshold': {'color': '#3a4456', 'class': 'emissive'},
        'beyond_wall': {'color': '#1c2232', 'class': 'emissive'}, 'riser': {'color': '#2a3040', 'class': 'emissive'},
        'beyond_hall': {'color': '#2c3448', 'class': 'emissive'}, 'beyond_jelly': {'color': '#4a3a78', 'class': 'emissive'},
        'beyond_tops': {'color': '#38404c', 'class': 'emissive'},
        'frame': {'color': '#202a3a'}, 'frame_top': {'color': '#3a4658'}, 'sill_top': {'color': '#2a4058'},
        'seam': {'color': '#1a2230'},
        'deck_edge': {'color': '#5a6474'},
        'bridge': emissive('#5a6470', f'{P}bridge', bits=4), 'feed_deck': emissive('#5a6470', f'{P}feed_deck', bits=4),
        'rail': {'color': '#a8b0bc', 'double_sided': True,
                 'texture': {'image': f'art/{P}rail.png', 'bits': 4, 'projection': 'box', 'scale': [1.0, 1.0]}},
        'hopper': {'color': '#6a7684'}, 'hopper_bin': {'color': '#8a949e'},
        'feed_top': {'color': '#6a5034', 'texture': {'image': f'art/{P}feed.png', 'bits': 4, 'projection': 'box',
                                                     'scale': [0.5, 0.5]}},
        'lamp': {'color': '#30343c'}, 'lens': {'color': '#fff2c8', 'class': 'emissive'},
        'bench': {'color': '#141c2c'}, 'bench_top': {'color': '#1a2a44'}, 'bench_foot': {'color': '#141a26'},
        'column': {'color': '#2e3a52'}, 'column_base': {'color': '#3a4a66'},
    }
    for name, *_ in floor_tiles():
        m[name] = emissive('#304060', P + name)
    for k in range(2):
        m[f'back_{k}'] = emissive('#303c50', f'{P}back_{k}')
        m[f'backwalk_{k}'] = emissive('#3a4250', f'{P}backwalk_{k}', bits=4)
    for k in range(4):
        m[f'rim_{k}'] = emissive('#5a6470', f'{P}rim_{k}', bits=4)
    nodes = shell_nodes() + window_nodes() + catwalk_nodes() + gallery_nodes()
    lighting = {'direction': [-0.2, 0.8, -0.55], 'ambient': 0.3, 'diffuse': 0.25, 'lights': room_lights(),
                'refine': {'tolerance': 22, 'max_added': 120}}
    return recipe(P + 'room', m, nodes, lighting, 1600)


# ---- the tank's life

def fish(mb, x, y, z, heading, length, width, mat):
    """A fish lying level, nose toward heading (degrees, 0 = +x, 90 = +z): a diamond body and a
    tail."""
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))

    def p(u, v):
        return (x + u * c - v * s, y, z + u * s + v * c)
    L, W = length, width
    mb.poly([p(L / 2, 0), p(0.05 * L, W / 2), p(-L * 0.3, 0), p(0.05 * L, -W / 2)], (0, 1, 0), mat)
    mb.poly([p(-L * 0.3, 0), p(-L / 2, W * 0.4), p(-L / 2, -W * 0.4)], (0, 1, 0), mat)


def tank_recipe():
    m = {
        'sand_0': emissive('#4a88aa', f'{P}sand_0'), 'sand_1': emissive('#4a88aa', f'{P}sand_1'),
        'tank_back': emissive('#1c4a78', f'{P}tank_back'),
        'glass': {'color': '#1c5c98', 'blend': 'add',
                  'texture': {'image': f'art/{P}glass.png', 'bits': 4, 'projection': 'fit'}},
        'rock': {'color': '#1e344c'}, 'rock_dark': {'color': '#142438'},
        'kelp': {'color': '#2a8a6a', 'double_sided': True,
                 'texture': {'image': f'art/{P}kelp.png', 'bits': 4, 'projection': 'fit'}},
        'sardine': {'color': '#dceeff', 'double_sided': True},
        'grouper': {'color': '#6a6050', 'double_sided': True},
        'eagle': {'color': '#2a3448', 'double_sided': True},
        'manta': {'color': '#16202e', 'double_sided': True},
    }
    for k in range(4):
        m[f'water_{k}'] = {'color': '#0c2a48', 'blend': 'half',
                           'texture': {'image': f'art/{P}water_{k}.png', 'bits': 4, 'projection': 'fit'}}
    n = []
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        n.append(box(f'sand_{k}', (a, -SLAB, WIN_Z1), (b, SAND_Y, BACK_Z0), 'rock_dark',
                     open=['bottom', 'left', 'right', 'back', 'front'], faces={'top': f'sand_{k}'}))
    n.append(box('tank_back', (X0, 0.2, BACK_Z0), (X1, U - DECK, ZO1), 'rock_dark',
                 open=['bottom', 'top', 'left', 'right', 'front'], faces={'back': 'tank_back'}))
    g = Mesh()
    gz = WIN_Z0 + 0.03
    g.quad_z(gz, X0 + PIER, X1 - PIER, 0.3, GLASS_TOP, -1, 'glass')
    n.append(g.node('glass', 'glass'))
    # the surface, in four chunks, half-blended
    w = Mesh()
    for k in range(4):
        a, b = X0 + 5 * k + (0.01 if k == 0 else 0), X0 + 5 * (k + 1) - (0.01 if k == 3 else 0)
        w.quad_y(WATER_Y, a, b, WIN_Z1, BACK_Z0, 1, f'water_{k}')
    n.append(w.node('surface', 'water_0'))
    rocks = []
    for k, (x, z, (sx, sy, sz)) in enumerate(ROCKS):
        rocks.append(at({'id': f'rock_{k}', 'op': 'sphere', 'radius': 1.0, 'rings': 4, 'segments': 7,
                         'material': 'rock' if k % 2 else 'rock_dark'},
                        translate=[x, SAND_Y + sy * 0.45, z], rotate=[0, (k * 37) % 60 - 30, 0]))
        rocks[-1]['transform']['scale'] = [sx, sy, sz]
    n.append({'id': 'rocks', 'op': 'group', 'children': rocks})
    kelp = Mesh()
    for (x, z, hgt) in ((-9.4, 1.5, 2.3), (-8.9, 1.62, 1.8), (-7.9, 1.45, 1.4), (8.6, 1.5, 2.2), (9.3, 1.6, 1.7),
                        (-7.6, 3.8, 2.5), (-5.6, 3.85, 2.4), (1.4, 3.85, 2.55), (4.2, 3.8, 2.3), (8.2, 3.85, 2.45)):
        kelp.quad_z(z, x - 0.17, x + 0.17, SAND_Y - 0.03, SAND_Y + hgt, -1, 'kelp')
    n.append(kelp.node('kelp', 'kelp'))
    life = Mesh()
    # the sardine school, a ribbon wheeling along the glass, low enough to show through it
    rng = np.random.default_rng(21)
    for k in range(64):
        t = k / 64
        x = -7.2 + t * 6.4 + rng.normal(0, 0.18)
        y = 0.95 + 0.45 * math.sin(t * 6.3) + rng.normal(0, 0.12)
        y = y if y > 0.6 else 0.6 + 0.007 * k
        z = 1.55 + 0.18 * math.cos(t * 6.3) + rng.normal(0, 0.06)
        fish(life, x, y, z, 10 + 25 * math.cos(t * 6.3) + rng.normal(0, 8), 0.28, 0.09, 'sardine')
    # a second school near the surface at the east end, seen from the catwalk
    for k in range(26):
        x = 2.2 + rng.random() * 3.4
        z = 3.05 + rng.random() * 0.75
        fish(life, x, 2.55 + rng.random() * 0.25, z, 190 + rng.normal(0, 10), 0.22, 0.07, 'sardine')
    for (x, y, z, hd, L) in ((6.4, 0.7, 1.6, 175, 0.9), (-8.3, 0.85, 1.55, 15, 0.8), (1.8, 0.55, 1.5, 200, 0.7)):
        fish(life, x, y, z, hd, L, L * 0.38, 'grouper')
    # an eagle ray low by the glass
    ex, ey, ez = 3.6, 1.05, 1.62
    for side in (1, -1):
        life.poly([(ex + 0.45, ey, ez), (ex - 0.05, ey + 0.03, ez + side * 0.55), (ex - 0.3, ey, ez)], (0, 1, 0), 'eagle')
    life.poly([(ex - 0.28, ey, ez - 0.02), (ex - 1.1, ey - 0.04, ez), (ex - 0.28, ey, ez + 0.02)], (0, 1, 0), 'eagle')
    # the manta, near the surface under the open water
    mx, my, mz = -3.2, 2.62, 3.3
    pts = [(mx + 0.7, my, mz), (mx + 0.15, my + 0.05, mz + 1.2), (mx - 0.35, my, mz + 0.3), (mx - 0.45, my, mz),
           (mx - 0.35, my, mz - 0.3), (mx + 0.15, my + 0.05, mz - 1.2)]
    for k in range(1, 5):
        life.poly([pts[0], pts[k], pts[k + 1]], (0, 1, 0), 'manta')
    life.poly([(mx - 0.42, my, mz - 0.02), (mx - 1.3, my - 0.03, mz + 0.05), (mx - 0.42, my, mz + 0.02)], (0, 1, 0), 'manta')
    life.poly([(mx + 0.7, my, mz - 0.18), (mx + 0.92, my, mz - 0.14), (mx + 0.7, my, mz - 0.05)], (0, 1, 0), 'manta')
    life.poly([(mx + 0.7, my, mz + 0.05), (mx + 0.92, my, mz + 0.14), (mx + 0.7, my, mz + 0.18)], (0, 1, 0), 'manta')
    n.append(life.node('life', 'sardine'))
    lighting = {'direction': [0.1, 1.0, -0.3], 'ambient': 0.5, 'diffuse': 0.5}
    return recipe(P + 'tank', m, n, lighting, 1000)


def wwater_recipe():
    """Agent W: the moving water (NOTES_W.md). The caustic net the window throws on the floor (its
    light box only), on the sand behind the glass and, from the water's light, up the back wall
    over the back walk; the glints on the surface under the catwalks, lit by the clamp lamps and
    the tank's own blue."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('net', 'w_caustic')
    ov.material('wall_net', 'w_caustic', axis='z', scale=[2.0, 1.0])
    ov.material('glint', 'w_ripple')
    bx0, bz0, bx1, bz1 = BAND
    ov.floor('net', 0.03, bx0 + 0.02, bx1 - 0.02, bz0 + 0.05, WIN_Z0 - 0.02, nx=4, nz=1)
    ov.floor('net', SAND_Y + 0.02, X0 + PIER, X1 - PIER, WIN_Z1 + 0.01, BACK_Z0 - 0.01, nx=4, nz=1)
    ov.floor('glint', WATER_Y + 0.03, X0 + 0.01, X1 - 0.01, WIN_Z1 + 0.01, BACK_Z0 - 0.01, nx=4, nz=1)
    ov.wall_z('wall_net', Z1 - 0.02, X0 + 0.01, X1 - 0.01, U + 0.02, U + 1.5, facing=-1, nx=4, ny=1)
    for k, x in enumerate((-7.5, -2.5, 2.5, 7.5)):
        ov.light((x, 1.2, 0.6), '#4aaaf0', 1.1, 2.4, id=f'window_{k}')
        ov.light((x, WATER_Y + 1.2, 2.7), '#4ab0e8', 0.8, 3.4, id=f'surface_{k}')
        ov.light((x, U - 0.3, Z1 - 0.9), '#3a9ad0', 0.9, 2.0, id=f'wall_{k}')
    for k, (lx, _) in enumerate(LAMPS):
        ov.light((lx, U + 0.85, RIM_Z1 - 0.5), '#ffd8a0', 1.8, 2.2, id=f'lamp_{k}')
    return ov.recipe(ART, refine={'tolerance': 24, 'max_added': 32})


def collision_recipe():
    rec = recipe(P + 'room_col', {'floor': {'color': '#8c9098'}}, aqroom.shell_nodes(D, collision=True), None, 400,
                 collision=True)
    return rec


def main():
    art = {}
    for name, a, b in floor_tiles():
        art[P + name] = paint_floor(a, b)
    for k, (a, b) in enumerate(((X0, 0.0), (0.0, X1))):
        art[f'{P}back_{k}'] = draw_gear(paint_back(a, b), a, b)
        art[f'{P}backwalk_{k}'] = paint_backwalk(a, b)
        art[f'{P}sand_{k}'] = paint_sand(a, b)
    for k in range(4):
        a, b = X0 + 5 * k, X0 + 5 * (k + 1)
        art[f'{P}rim_{k}'] = paint_grate(a, b, RIM_Z0, RIM_Z1, 160, 42, RIM_LIGHTS, rim_edge=True)
        art[f'{P}water_{k}'] = paint_water(a, b)
    bx0, bz0, bx1, bz1 = G.BRIDGES[0]
    art[P + 'bridge'] = paint_grate(bx0, bx1, bz0, bz1, 40, 46, along='z')
    fa, fza, fb, fzb = G.FEED
    art[P + 'feed_deck'] = paint_grate(fa, fb, fza, fzb, 64, 22)
    art.update({P + 'section': paint_section(XO0, XO1), P + 'rail': paint_rail(), P + 'tank_back': paint_tank_back(),
                P + 'glass': paint_glass(), P + 'kelp': paint_kelp(), P + 'feed': paint_feed()})
    for name, img in art.items():
        save_png(img, ART / f'{name}.png')
    for rec in (room_recipe(), tank_recipe(), wwater_recipe(), collision_recipe()):     # agent W: wwater
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    placements = [{'id': P + 'room', 'asset': P + 'room', 'position': [0, 0, 0], 'collision': P + 'room_col'},
                  {'id': P + 'tank', 'asset': P + 'tank', 'position': [0, 0, 0], 'collision': 'none'},
                  {'id': P + 'wwater', 'asset': P + 'wwater', 'position': [0, 0, 0], 'collision': 'none'}]  # agent W
    write_json(HERE / 'aq_great.placements.json',
               {'format': 'after-hours-placements', 'version': 1, 'room': 'aq_great', 'placements': placements})


if __name__ == '__main__':
    main()
