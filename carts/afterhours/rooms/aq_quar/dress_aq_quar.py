#!/usr/bin/env python3
"""The aquarium, room 4: quarantine, dressed. Writes the room's Asset Kit recipes into dressed/,
their textures into dressed/art/ and aq_quar.placements.json beside this script
(--no-placements leaves the placements alone).

    python3 carts/afterhours/rooms/aq_quar/dress_aq_quar.py

Behind the public galleries, through the staff door: where sick and newly arrived animals are
kept apart. Dark, clinical, humming:

- two long rows of holding tanks on steel stands, five tanks a row, bare-bottomed, their water
  faintly violet: a sick ray with pale patches, a moray in a length of pipe, an octopus under a
  lid weighted shut, a pufferfish, a horseshoe crab, sea stars, a shoal of small fish, one tank
  drained for cleaning; white tubs with coloured tape on the stands' lower shelves;
- an ultraviolet steriliser along the back of each row, its tube glowing violet (the rows take
  turns, every three seconds: the floor's two violet patches are the play file's two light boxes,
  painted at half strength so that the runtime's wash shows which is on);
- the filter cabinets at the rows' east ends, their louvres and status lamps;
- the keeper's desk in the front corner: a log book, a microscope, a rack of sample tubes, a
  thermos, the lamp off;
- the floor dark sealed concrete, drain gutters along the rows (the violet patches' edges), a
  disinfectant footbath at the way in;
- on the back wall, white tiles in the dark: a whiteboard of the tanks' pictograms and ticks,
  a clock, the hygiene pictograms by the door, a hose reel;
- the stair lamp over the east door, the only steady light, and the stair going down beyond it
  to the plant; the staff passage from the ocean gallery beyond the west door.

The floor plan is the level lead's (PLAN.md, make_aq_quar.py), imported for its numbers. What
looks lit is lit: nothing on the floor is bright outside the play file's light boxes.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'water'))   # agent W: the moving water (NOTES_W.md)
import wateranim  # noqa: E402
import make_aq_quar as G  # noqa: E402  (the lead's plan: imported for its numbers only)
from aqdress import (CUT_H, Mesh, Room, at, beyond_flight, blob, box, box_light, collision_recipe, grid, prune,  # noqa: E402
                     kit_lighting, mat_tex, paint_rgb, paint_section, paint_wall, placements_file, r, rect,
                     recipe, save_art, smoothstep, to_image, vram, wet, write_json)

OUT = HERE / 'dressed'
ART = OUT / 'art'
P = 'qt_'
R = Room(G.ROOM, P)
ROWS = {'a': G.ROW_A, 'b': G.ROW_B}
PROPS = {p[0]: p[2] for p in G.ROOM['props']}
LIGHTS = {lid: bx for lid, bx, lvl, cyc in G.ROOM['lights']}
DESK = PROPS['desk']
STAND = 0.48           # the stands' top: the tanks' glass stands on it
GLASS_TOP = 0.97       # the tanks' rims, under the section's cut
WATER = 0.9
TANKS = 5              # a row
LEGS = (-4.15, -1.4, 1.4, 4.15)
GUTTERS = (1.0, -1.8)  # drain gutters along the rows: where the two violet boxes meet and begin
FOOTBATH = (-6.45, 1.95, -5.75, 2.85)
STAIR_LAMP = (6.42, 2.2, -2.8)

UV = np.array([0.62, 0.36, 1.10])        # an ultraviolet box's light at half strength (the paint)
EXIT = np.array([1.30, 1.28, 1.08])      # the stair lamp, steady, full strength
DARK = np.array([0.15, 0.16, 0.23])      # the rest of the room


def tank_spans(row):
    x0, z0, x1, z1 = row
    w = (x1 - x0) / TANKS
    return [(x0 + k * w + 0.035, z0 + 0.04, x0 + (k + 1) * w - 0.035, z1 - 0.04) for k in range(TANKS)]


def kit_lights():
    """For the props' bake (the painted floor and wall are painted from the same places)."""
    out = []
    for name, (x0, z0, x1, z1) in ROWS.items():
        for k, x in enumerate((-2.8, 0.0, 2.8)):
            out.append({'id': f'uv_{name}{k}', 'at': [x, 1.25, z1 - 0.1], 'color': '#9a6cff', 'intensity': 0.9,
                        'range': 2.6})
    out.append({'id': 'stair', 'at': list(STAIR_LAMP), 'color': '#f0f0d8', 'intensity': 1.6, 'range': 3.6})
    out.append({'id': 'passage', 'at': [-7.6, 1.6, 2.4], 'color': '#5a8ad8', 'intensity': 0.8, 'range': 2.2})
    return out


# ---- painting

def caustics(x, z, scale=1.0, seed=0.0):
    """A caustic net: bright thin lines, 0..1 (as the ocean gallery's floor has)."""
    x = x * scale
    z = z * scale
    a = np.sin(x * 2.1 + np.sin(z * 1.7 + seed) * 1.4 + seed)
    b = np.sin(z * 2.6 + np.sin(x * 1.3 - seed) * 1.2 - seed * 0.5)
    c = np.sin((x + z) * 1.6 + np.sin((x - z) * 1.1 + seed) * 1.1)
    return np.clip(1 - np.abs((a + b + c) / 3.0) * 2.6, 0, 1) ** 3


def floor_base(x, z):
    """The floor in white light: dark green-grey sealed concrete, trowel marks, the gutters, the
    footbath, wet under the tanks, a round drain by the desk."""
    h, w = x.shape
    rng = np.random.default_rng(int(abs(x[0, 0] * 7 + z[0, 0] * 3)) + 11)
    base = np.zeros((h, w, 3)) + np.array([118, 132, 128]) + (rng.random((h, w)) - 0.5)[..., None] * 10
    base *= (1 + 0.04 * np.sin(x * 2.3 + np.sin(z * 1.7) * 2))[..., None]
    # bay joints every 3.25 m
    base *= np.where(np.abs(((x + 6.5) / 3.25) % 1 - 0.5) > 0.493, 0.82, 1.0)[..., None]
    # wet under and in front of the tanks
    for (x0, z0, x1, z1) in ROWS.values():
        base *= (1 - 0.22 * rect(x, z, x0 - 0.1, z0 - 0.25, x1 + 0.1, z1 + 0.1, soft=0.15))[..., None]
    for k, (cx, cz) in enumerate(((-2.4, -1.75), (1.9, 0.75), (3.3, 2.35), (-3.6, 0.9))):
        base *= (1 - 0.18 * wet(x, z, cx, cz, 0.5, 0.3, k))[..., None]
    # the gutters: a steel grate in a dark channel, along the rows
    for gz in GUTTERS:
        g = (np.abs(z - gz) < 0.07) & (x > -4.4) & (x < 4.4)
        base = paint_rgb(base, g, (40, 44, 46))
        base = paint_rgb(base, g & (((x * 25) % 1) < 0.45) & (np.abs(z - gz) < 0.05), (150, 156, 160))
    # a round floor drain by the desk
    d = np.hypot(x + 4.3, z + 2.3)
    base = paint_rgb(base, d < 0.13, (60, 64, 66))
    base = paint_rgb(base, (d < 0.11) & (((x + z) * 30) % 1 < 0.4), (150, 156, 160))
    # the disinfectant footbath at the way in: a grey tray of violet-pink water
    fx0, fz0, fx1, fz1 = FOOTBATH
    base = paint_rgb(base, rect(x, z, fx0, fz0, fx1, fz1) > 0, (96, 100, 104))
    base = paint_rgb(base, rect(x, z, fx0 + 0.06, fz0 + 0.06, fx1 - 0.06, fz1 - 0.06) > 0, (176, 92, 150))
    # a yellow line round the clean zone's door
    base = paint_rgb(base, (np.abs(x + 5.6) < 0.03) & (z > 1.6) & (z < 3.2), (196, 170, 60))
    return base


def floor_shade(x, z):
    """The floor's light: the two ultraviolet boxes at half strength, the stair lamp's box at full
    strength, nothing else."""
    shade = np.zeros(x.shape + (3,)) + DARK
    for lid in ('uv_a', 'uv_b'):
        k = box_light(x, z, LIGHTS[lid], soft=0.22)
        row = ROWS[lid[-1]]
        # a little brighter just in front of the row its steriliser is on
        near = np.exp(-((z - (row[1] - 0.2)) / 0.9) ** 2) * 0.18
        # the tanks' water throws a faint violet net on the floor beside them
        caus = 0.13             # agent W: the net moves (aq_wwater's overlay); the floor keeps its average, a little under
        tank = np.exp(-(np.maximum(0, np.maximum(row[1] - z, z - row[3])) / 0.6) ** 2)
        glint = (0.85 + 0.55 * caus * tank)[..., None]
        shade += k[..., None] * (UV * (0.88 + near[..., None]) * glint - DARK)
    k = box_light(x, z, LIGHTS['exit'], soft=0.3)
    lx, _, lz = STAIR_LAMP
    fall = 0.72 + 0.45 * np.exp(-((x - lx) ** 2 + (z - lz) ** 2) / 1.6)
    shade += k[..., None] * (EXIT * fall[..., None] - DARK)
    # the tank stands' shadow under them (inside the boxes, so it stays lit)
    for (x0, z0, x1, z1) in ROWS.values():
        shade *= (1 - 0.25 * rect(x, z, x0 + 0.05, z0 + 0.05, x1 - 0.05, z1 - 0.05, soft=0.08))[..., None]
    # the filter cabinets' and the desk's own darkness
    for nm in ('filter_a', 'filter_b', 'desk'):
        x0, z0, x1, z1 = PROPS[nm]
        shade *= (1 - 0.3 * rect(x, z, x0, z0, x1, z1, soft=0.05))[..., None]
    return shade


def paint_floor_tile(x0, x1, z0, z1, w=255, h=127):
    x, z = grid(x0, x1, z0, z1, w, h)
    rgb = floor_base(x, z) * floor_shade(x, z) / 1.0
    # the room's edges a little darker (where the walls meet the floor)
    d = np.minimum.reduce([x - R.X0, R.X1 - x, z - R.Z0, R.Z1 - z])
    rgb *= (1 - 0.3 * np.exp(-np.clip(d, 0, None) / 0.15))[..., None]
    # the status lamps' pinpricks reflected under the cabinets (inside nothing: tiny, not light)
    return to_image(rgb, dither=4.0)


def wall_lights():
    return [{'id': f'uv_{k}', 'at': [x, 1.0, 1.7], 'color': '#8a5cff', 'intensity': 0.55, 'range': 3.4}
            for k, x in enumerate((-3.0, 0.0, 3.0))] + \
           [{'id': 'stair', 'at': [6.2, 2.2, -2.8], 'color': '#f0f0d8', 'intensity': 0.5, 'range': 7.6}]


WB = (-2.4, 0.4, 1.05, 1.85)       # the whiteboard on the back wall: x0, x1, y0, y1
CLOCK = (1.4, 1.95)
REEL = (3.6, 1.25)
PICTOS = (-5.3, 1.45)


def wall_base(x, y):
    """The back wall in white light: white tiles in a grid, a dark skirting, the whiteboard, the
    clock, the hygiene pictograms by the way in, the hose reel."""
    h, w = x.shape
    base = np.zeros((h, w, 3)) + np.array([198, 204, 210])
    grout = (np.abs(((x + 6.75) / 0.2) % 1 - 0.5) > 0.44) | (np.abs((y / 0.2) % 1 - 0.5) > 0.44)
    base = np.where(grout[..., None], base * 0.84, base)
    base = np.where((y < 0.12)[..., None], np.array([70, 76, 84]), base)
    # the whiteboard: an aluminium frame, the board, a grid of the ten tanks with pictograms
    x0, x1, y0, y1 = WB
    base = paint_rgb(base, rect(x, y, x0 - 0.04, y0 - 0.04, x1 + 0.04, y1 + 0.04) > 0, (150, 154, 160))
    base = paint_rgb(base, rect(x, y, x0, y0, x1, y1) > 0, (236, 238, 240))
    cw = (x1 - x0 - 0.1) / 5
    for row in range(2):
        for k in range(5):
            cx = x0 + 0.05 + cw * (k + 0.5)
            cy = y1 - 0.2 - row * 0.36
            # the cell's lines
            base = paint_rgb(base, (np.abs(x - (cx - cw / 2)) < 0.006) & (y > y0 + 0.06) & (y < y1 - 0.04), (60, 70, 120))
            # an animal's outline in marker: a blob with a tail, each its own
            ang = [0.0, 0.6, -0.4, 0.2, 1.2, -0.8, 0.4, 0.9, -0.2, 0.7][row * 5 + k]
            dx, dy = (x - cx) * math.cos(ang) - (y - cy) * math.sin(ang), (x - cx) * math.sin(ang) + (y - cy) * math.cos(ang)
            body = np.abs(np.hypot(dx / 0.075, dy / 0.04) - 1) < 0.25
            base = paint_rgb(base, body, [(40, 60, 160), (40, 60, 160), (190, 40, 40), (40, 60, 160), (30, 120, 70)][(row + k) % 5])
            # the ticks and the dosing marks under it
            for t in range(3 + (k % 2)):
                tk = (np.abs(x - (cx - 0.08 + t * 0.05)) < 0.012) & (np.abs(y - (cy - 0.11)) < 0.02)
                base = paint_rgb(base, tk, (190, 40, 40) if (row + k + t) % 4 == 0 else (40, 60, 160))
    # magnets
    for k, mx in enumerate((-2.25, -1.1, 0.1)):
        base = paint_rgb(base, np.hypot(x - mx, y - (y1 - 0.06)) < 0.025, [(220, 60, 60), (60, 120, 220), (240, 200, 60)][k])
    # the clock
    cx, cy = CLOCK
    d = np.hypot(x - cx, y - cy)
    base = paint_rgb(base, d < 0.17, (60, 64, 72))
    base = paint_rgb(base, d < 0.15, (236, 238, 232))
    base = paint_rgb(base, (np.abs(x - cx) < 0.01) & (y > cy) & (y < cy + 0.11), (30, 30, 30))
    base = paint_rgb(base, (np.abs(y - cy) < 0.01) & (x > cx) & (x < cx + 0.08), (30, 30, 30))
    # the hygiene pictograms by the way in: wash hands, boots, no entry for the unauthorised
    px, py = PICTOS
    for k in range(3):
        sx = px + k * 0.38
        base = paint_rgb(base, rect(x, y, sx - 0.15, py - 0.15, sx + 0.15, py + 0.15) > 0,
                         [(40, 110, 200), (40, 110, 200), (200, 50, 50)][k])
        base = paint_rgb(base, rect(x, y, sx - 0.12, py - 0.12, sx + 0.12, py + 0.12) > 0, (240, 242, 244))
    s0 = px
    base = paint_rgb(base, (np.hypot(x - s0, y - (py + 0.02)) < 0.07) & (y > py - 0.02), (40, 110, 200))  # a hand under a tap
    base = paint_rgb(base, rect(x, y, s0 - 0.02, py - 0.1, s0 + 0.02, py - 0.04) > 0, (40, 110, 200))
    s1 = px + 0.38
    base = paint_rgb(base, rect(x, y, s1 - 0.05, py - 0.09, s1 + 0.02, py + 0.08) > 0, (40, 110, 200))  # a boot
    base = paint_rgb(base, rect(x, y, s1 - 0.05, py - 0.09, s1 + 0.09, py - 0.03) > 0, (40, 110, 200))
    s2 = px + 0.76
    ring = np.abs(np.hypot(x - s2, y - py) - 0.09) < 0.02
    slash = (np.abs((x - s2) + (y - py)) < 0.02) & (np.hypot(x - s2, y - py) < 0.09)
    base = paint_rgb(base, ring | slash, (200, 50, 50))
    # the hose reel: a red drum on a bracket
    hx, hy = REEL
    d = np.hypot(x - hx, y - hy)
    base = paint_rgb(base, d < 0.26, (170, 40, 36))
    base = paint_rgb(base, np.abs(d - 0.16) < 0.03, (230, 210, 190))
    base = paint_rgb(base, d < 0.05, (60, 30, 30))
    # the stair's green emergency sign by the east door (a running figure and a door)
    ex, ey = 6.0, 2.15
    base = paint_rgb(base, rect(x, y, ex - 0.22, ey - 0.08, ex + 0.22, ey + 0.08) > 0, (40, 180, 100))
    base = paint_rgb(base, rect(x, y, ex + 0.06, ey - 0.06, ex + 0.17, ey + 0.06) > 0, (236, 255, 240))
    base = paint_rgb(base, np.hypot(x - (ex - 0.08), y - (ey + 0.035)) < 0.02, (236, 255, 240))
    base = paint_rgb(base, (np.abs((x - (ex - 0.08)) * 0.6 + (y - ey)) < 0.012) & (np.abs(x - (ex - 0.08)) < 0.06), (236, 255, 240))
    return base


def wall_extra(x, y, rgb):
    # the sign glows of itself; the violet catches the white tile's glaze in a band
    ex, ey = 6.0, 2.15
    rgb = np.where((rect(x, y, ex - 0.22, ey - 0.08, ex + 0.22, ey + 0.08) > 0)[..., None],
                   rgb * 0.3 + np.array([40, 190, 110]), rgb)
    rgb = rgb + (blob(x, y, ex, ey, 0.5, 0.2) * 0.18)[..., None] * np.array([40, 255, 120])
    return rgb


def paint_ripple(n=32):
    """The tanks' water: a violet sheen in quarter blend (black adds nothing)."""
    xs = (np.arange(n) + 0.5) / n * 2 * math.pi
    x, z = np.meshgrid(xs, xs)
    v = (np.sin(x + np.sin(z * 2) * 0.8) + np.sin(z * 2 + np.sin(x) * 1.2 + 1) + np.sin((x + z) + 2)) / 3
    c = np.clip(1 - np.abs(v) * 2.4, 0, 1) ** 2
    rgb = np.array([22, 10, 52]) + c[..., None] * np.array([120, 90, 200])
    return to_image(rgb, 0)


def paint_cabinet(w=24, h=32):
    """A filter cabinet's front: louvres, two status lamps, a dial, a hazard sticker (no words)."""
    img = Image.new('RGB', (w, h), (120, 128, 136))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(70, 76, 84))
    for k in range(6):
        d.line([(3, 12 + k * 3), (w - 4, 12 + k * 3)], fill=(60, 66, 74))
    d.rectangle([3, 3, 7, 7], fill=(40, 230, 120))
    d.rectangle([9, 3, 13, 7], fill=(230, 160, 40))
    d.ellipse([16, 2, 21, 7], fill=(230, 232, 228), outline=(40, 40, 40))
    d.line([(18, 5), (20, 3)], fill=(200, 40, 40))
    d.polygon([(w // 2, h - 8), (w // 2 - 4, h - 2), (w // 2 + 4, h - 2)], fill=(240, 200, 40))
    return img


def paint_tub(w=16, h=8, col=(220, 60, 60)):
    """A white tub's side with a coloured tape label and marker strokes."""
    img = Image.new('RGB', (w, h), (214, 218, 222))
    d = ImageDraw.Draw(img)
    d.rectangle([3, 2, 12, 5], fill=col)
    d.line([(5, 3), (10, 4)], fill=(30, 30, 40))
    d.line([(0, 0), (w, 0)], fill=(170, 176, 182))
    return img


def paint_card(k, w=12, h=8):
    """A tank's card: white, a coloured band, an animal's outline, the doses as dots."""
    img = Image.new('RGB', (w, h), (232, 234, 240))
    d = ImageDraw.Draw(img)
    col = [(220, 60, 60), (60, 120, 220), (240, 190, 50), (70, 170, 90)][k]
    d.rectangle([0, 0, w - 1, 1], fill=col)
    d.ellipse([2, 3, 6, 6], outline=(40, 50, 90))
    for j in range(k % 3 + 1):
        d.point((8 + j, 4), fill=col)
    return img


def paint_log(w=16, h=12):
    """The keeper's log book open, from above: ruled pages, a column of ticks."""
    img = Image.new('RGB', (w, h), (232, 230, 220))
    d = ImageDraw.Draw(img)
    for k in range(2, h, 2):
        d.line([(1, k), (6, k)], fill=(120, 130, 170))
        d.line([(9, k), (14, k)], fill=(120, 130, 170))
    d.line([(7, 0), (8, h)], fill=(150, 146, 136))
    d.point([(12, 3), (12, 7)], fill=(200, 40, 40))
    return img


def paint_rack(w=16, h=4):
    img = Image.new('RGB', (w, h), (60, 64, 72))
    cols = [(230, 80, 80), (80, 200, 230), (240, 220, 80), (150, 230, 120), (230, 120, 220)]
    for k in range(7):
        img.putpixel((1 + k * 2, 1), cols[k % 5])
        img.putpixel((1 + k * 2, 2), cols[k % 5])
    return img


# ---- the recipes

def stand_nodes():
    n = []
    for name, (x0, z0, x1, z1) in ROWS.items():
        n.append(box(f'stand_{name}', (x0, STAND - 0.06, z0), (x1, STAND, z1), 'stand'))
        n.append(box(f'shelf_{name}', (x0 + 0.05, 0.1, z0 + 0.05), (x1 - 0.05, 0.14, z1 - 0.05), 'stand_dark'))
        for k, lx in enumerate(LEGS):
            for j, lz in enumerate((z0 + 0.05, z1 - 0.05)):
                n.append(box(f'leg_{name}{k}{j}', (lx - 0.03, -0.02, lz - 0.03), (lx + 0.03, STAND - 0.059, lz + 0.03),
                             'stand', open=['bottom', 'top']))
        # tubs on the lower shelf, each with its coloured tape
        for k, (tx, tw) in enumerate(((-3.5, 0.5), (-2.9, 0.45), (-0.6, 0.55), (2.1, 0.45), (2.65, 0.4), (3.3, 0.5))):
            if (k + (name == 'a')) % 3 == 2:
                continue
            n.append(box(f'tub_{name}{k}', (tx, 0.139, z0 + 0.12), (tx + tw, 0.36 + 0.03 * (k % 2), z1 - 0.12),
                         'tub', open=['bottom'], faces={'back': f'tub_{k % 3}', 'top': 'tub_lid' if k % 2 else 'tub_in'}))
        # the ultraviolet steriliser along the row's back: a housing, its tube glowing
        n.append(box(f'uv_{name}', (x0 + 0.05, GLASS_TOP - 0.05, z1 - 0.13), (x1 - 0.05, 0.995, z1 - 0.03), 'uv_housing',
                     faces={'back': 'uv_tube', 'top': 'uv_top'}))
        # the tanks' black rims, standing on the stand
        for k, (tx0, tz0, tx1, tz1) in enumerate(tank_spans((x0, z0, x1, z1))):
            n.append(box(f'base_{name}{k}', (tx0 - 0.03, STAND, tz0 - 0.03), (tx1 + 0.03, STAND + 0.05, tz1 + 0.03),
                         'rim', open=['bottom', 'top']))
            n.append(box(f'trim_{name}{k}', (tx0 - 0.03, GLASS_TOP - 0.03, tz0 - 0.03), (tx1 + 0.03, GLASS_TOP, tz1 + 0.03),
                         'rim', open=['bottom', 'top']))
            # the tank's card, clipped to its glass: a pictogram and coloured dots for the doses
            cx = tx0 + 0.25
            n.append(box(f'card_{name}{k}', (cx - 0.1, 0.6, tz0 - 0.06), (cx + 0.1, 0.74, tz0 - 0.045), 'card_edge',
                         faces={'back': f'card_{(k + (name == "a") * 2) % 4}'}))
    return n


def cabinet_nodes():
    n = []
    for nm in ('filter_a', 'filter_b'):
        x0, z0, x1, z1 = PROPS[nm]
        n.append(box(nm, (x0, -0.02, z0), (x1, CUT_H, z1), 'cabinet', open=['bottom'],
                     faces={'top': 'cut', 'back': 'cab_face', 'left': 'cab_face'}))
        # the return pipe from the cabinet into the row's last tank, and a valve wheel
        zc = (z0 + z1) / 2
        n.append(box(f'{nm}_pipe', (x0 - 0.12, 0.78, zc + 0.05), (x0 + 0.01, 0.84, zc + 0.11), 'pvc', open=['right']))
        n.append(at({'id': f'{nm}_valve', 'op': 'cylinder', 'radius': 0.06, 'height': 0.03, 'segments': 6,
                     'material': 'valve'}, translate=[x0 - 0.06, 0.852, zc + 0.08]))
    return n


def desk_nodes():
    x0, z0, x1, z1 = DESK
    n = [box('desk_top', (x0, 0.74, z0), (x1, 0.78, z1), 'desk_top_side', open=['left', 'back'], faces={'top': 'desk_top'}),
         box('desk_pedestal', (x1 - 0.48, -0.02, z0), (x1 - 0.02, 0.741, z1 - 0.04), 'desk', open=['bottom', 'back'],
             faces={'right': 'drawers'}),
         box('desk_leg', (x0 + 0.05, -0.02, z1 - 0.1), (x0 + 0.1, 0.741, z1 - 0.05), 'desk', open=['bottom', 'top']),
         at({'id': 'stool', 'op': 'cylinder', 'radius': 0.17, 'height': 0.05, 'segments': 8, 'material': 'stool'},
            translate=[-5.85, 0.45, -3.3]),
         at({'id': 'stool_leg', 'op': 'cylinder', 'radius': 0.03, 'height': 0.44, 'segments': 4, 'caps': False,
             'material': 'desk'}, translate=[-5.85, 0.21, -3.3]),
         # the log book open, a clipboard, the microscope, the rack of tubes, a thermos, the lamp off
         box('log', (-6.2, 0.779, -3.75), (-5.72, 0.8, -3.42), 'paper_side', faces={'top': 'log'}),
         box('clipboard', (-5.6, 0.779, -3.6), (-5.36, 0.795, -3.25), 'clip', faces={'top': 'paper'}),
         box('scope_base', (-5.15, 0.779, -3.85), (-4.95, 0.81, -3.65), 'scope'),
         box('scope_arm', (-5.09, 0.8, -3.86), (-5.03, 1.0 - 0.005, -3.8), 'scope', open=['bottom']),
         at({'id': 'scope_head', 'op': 'box', 'size': [0.07, 0.07, 0.16], 'material': 'scope'},
            translate=[-5.06, 0.9, -3.72], rotate=[-35, 0, 0]),
         box('rack', (-5.3, 0.779, -3.25), (-4.9, 0.86, -3.12), 'rack_side', faces={'top': 'rack'}),
         at({'id': 'thermos', 'op': 'cylinder', 'radius': 0.045, 'height': 0.2, 'segments': 6, 'material': 'thermos'},
            translate=[-6.32, 0.885, -3.2]),
         box('lamp_base', (-6.35, 0.779, -3.92), (-6.2, 0.8, -3.78), 'lamp'),
         at({'id': 'lamp_arm', 'op': 'box', 'size': [0.03, 0.2, 0.03], 'material': 'lamp'},
            translate=[-6.25, 0.875, -3.81], rotate=[25, 0, 0]),
         at({'id': 'lamp_head', 'op': 'cone', 'radius': 0.07, 'height': 0.09, 'segments': 6, 'material': 'lamp'},
            translate=[-6.25, 0.92, -3.7], rotate=[180, 0, 0])]
    return n


def room_recipe():
    tiles = R.floor_tiles(2, 2)
    chunks = R.back_chunks(7.0)
    m = R.shell_materials()
    m['cut'] = {'color': '#3c475e', 'class': 'emissive'}
    m['section'] = mat_tex(P + 'section', '#3a4254', bits=4)
    for name, *_ in tiles:
        m[name] = mat_tex(P + name, '#2a2a40')
    for name, *_ in chunks:
        m[name] = mat_tex(P + name, '#3a3850')
    m.update({
        'wall_in': {'color': '#4a5060'}, 'end': {'color': '#5c6272'}, 'reveal': {'color': '#545a6a'},
        'lintel': {'color': '#8a90a0'}, 'door_glow': {'color': '#8a90a8', 'class': 'emissive'},
        'threshold': {'color': '#2c3448', 'class': 'emissive'}, 'beyond_wall': {'color': '#262c3e', 'class': 'emissive'},
        'tread': {'color': '#6a6a60', 'class': 'emissive'}, 'riser': {'color': '#3a3a36', 'class': 'emissive'},
        'stand': {'color': '#8a92a0'}, 'stand_dark': {'color': '#5a6270'}, 'rim': {'color': '#1c1e26'},
        'tub': {'color': '#c8ccd0'}, 'tub_lid': {'color': '#4a7ac0'}, 'tub_in': {'color': '#3a5a6a'},
        'uv_housing': {'color': '#6a7080'}, 'uv_tube': {'color': '#c890ff', 'class': 'emissive'},
        'uv_top': {'color': '#6c4aa8', 'class': 'emissive'},
        'cabinet': {'color': '#8a929c'}, 'cab_face': mat_tex(P + 'cabinet', '#78808a', bits=4, emissive=False),
        'pvc': {'color': '#9aa2aa'}, 'valve': {'color': '#c04040'},
        'desk': {'color': '#7a8290'}, 'desk_top': {'color': '#8a92a0'}, 'desk_top_side': {'color': '#6a7280'},
        'drawers': {'color': '#727a88'}, 'stool': {'color': '#3a4a6a'},
        'paper_side': {'color': '#c8c4b8'}, 'log': mat_tex(P + 'log', '#d0ccc0', bits=4, emissive=False),
        'clip': {'color': '#6a5040'}, 'paper': {'color': '#dcdcd4'}, 'scope': {'color': '#3a3e48'},
        'rack_side': {'color': '#4a4e58'}, 'rack': mat_tex(P + 'rack', '#606470', bits=4, emissive=False),
        'thermos': {'color': '#b03838'}, 'lamp': {'color': '#2e323c'}, 'card_edge': {'color': '#b0b0c0'},
    })
    for k in range(4):
        m[f'card_{k}'] = mat_tex(f'{P}card_{k}', '#b0a8d8', bits=4)
    for k, col in enumerate(((220, 60, 60), (60, 120, 220), (240, 190, 50))):
        m[f'tub_{k}'] = mat_tex(f'{P}tub_{k}', '#c8ccd0', bits=4, emissive=False)
    n = R.floor_nodes(tiles) + R.wall_nodes(chunks)
    n += [beyond_flight(R, 'ocean', 0, landing=1.4, threshold='threshold', side_wall='beyond_wall'),
          beyond_flight(R, 'plant', -6, landing=0.45, threshold='stair_landing', side_wall='stair_wall',
                        fade=['stair_0', 'stair_1', 'stair_2', 'stair_3', 'stair_4', 'stair_5'])]
    m.update({'stair_landing': {'color': '#8a8a7c', 'class': 'emissive'}, 'stair_wall': {'color': '#4a4c50', 'class': 'emissive'}})
    for k, c in enumerate(('#7a7a6e', '#66665c', '#52524a', '#40403a', '#30302c', '#222220')):
        m[f'stair_{k}'] = {'color': c, 'class': 'emissive'}
    # the stair lamp over the east doorway: a caged bulkhead on the end wall's inner face
    lx, ly, lz = STAIR_LAMP
    n.append(box('stair_lamp', (R.X1 - 0.08, ly - 0.07, lz - 0.16), (R.X1 + 0.01, ly + 0.07, lz + 0.16), 'lamp_cage',
                 open=['right'], faces={'left': 'lamp_glow', 'back': 'lamp_glow', 'bottom': 'lamp_glow'}))
    m.update({'lamp_cage': {'color': '#4a4e56'}, 'lamp_glow': {'color': '#fff4d0', 'class': 'emissive'}})
    props = stand_nodes() + cabinet_nodes() + desk_nodes()
    lighting = kit_lighting(kit_lights(), 0.08, {'tolerance': 24, 'max_added': 60})
    # the shell (floor, walls, the ways on) and the furniture apart: the shell alone fits the kit's
    # stand-in cap (700 triangles), so a far view of the room still has its floor and walls
    return (recipe(P + 'room', prune(m, n), n, lighting, 1000),
            recipe(P + 'props', prune(m, props), props, kit_lighting(kit_lights(), 0.08, {'tolerance': 24, 'max_added': 80}), 1200))


def fish(mesh, cx, cy, cz, heading, length, width, mat, tail=True):
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))

    def p(u, w):
        return (cx + u * c - w * s, cy, cz + u * s + w * c)
    L, W = length / 2, width / 2
    mesh.poly([p(L, 0), p(0.1 * L, W), p(-0.55 * L, 0), p(0.1 * L, -W)], (0, 1, 0), mat)
    if tail:
        mesh.poly([p(-0.55 * L, 0), p(-L * 1.05, W * 0.9), p(-L * 1.05, -W * 0.9)], (0, 1, 0), mat)


def ray_shape(mesh, cx, cy, cz, heading, span, mat, spot):
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))

    def p(u, w):
        return (cx + u * c - w * s, cy, cz + u * s + w * c)
    h = span / 2
    mesh.poly([p(h * 0.75, 0), p(0, h), p(-h * 0.5, 0), p(0, -h)], (0, 1, 0), mat)
    mesh.poly([p(-h * 0.5, 0.0), p(-h * 1.6, 0.015), p(-h * 1.6, -0.015)], (0, 1, 0), mat)
    # the pale patches of its illness
    def q(u, w):
        x, y, z = p(u, w)
        return (x, y + 0.012, z)
    mesh.poly([q(0.05, h * 0.3), q(0.12, h * 0.45), q(0.0, h * 0.5), q(-0.05, h * 0.35)], (0, 1, 0), spot)
    mesh.poly([q(-0.1, -h * 0.2), q(-0.02, -h * 0.3), q(-0.1, -h * 0.4)], (0, 1, 0), spot)


def star(mesh, cx, cy, cz, rad, mat, rot=0.0):
    pts = []
    for k in range(10):
        a = math.radians(rot + k * 36)
        rr = rad if k % 2 == 0 else rad * 0.4
        pts.append((cx + rr * math.cos(a), cy, cz + rr * math.sin(a)))
    mesh.poly(pts, (0, 1, 0), mat)


def tanks_recipe():
    m = {'glass': {'color': '#6a58d0', 'blend': 'quarter', 'double_sided': True},
         'surface': {'color': '#5a3aa8', 'blend': 'quarter',      # agent W: the sheen moves
                     'texture': wateranim.texture(wateranim.key('w_ripple', '#9a6ce8', base='#1a0c40'))},
         'bottom': {'color': '#30296c', 'class': 'emissive'},
         'bottom_dry': {'color': '#3a3e50', 'class': 'emissive'},
         'ray': {'color': '#9a8ad8', 'class': 'emissive', 'double_sided': True},
         'ray_spot': {'color': '#e8e0ff', 'class': 'emissive', 'double_sided': True},
         'moray': {'color': '#5a9a6a', 'class': 'emissive', 'double_sided': True},
         'pipe_hide': {'color': '#6a6a8a', 'class': 'emissive'},
         'octopus': {'color': '#c06a7a', 'class': 'emissive', 'double_sided': True},
         'lid': {'color': '#3a3a4a'}, 'weight': {'color': '#8a8a9a'},
         'puffer': {'color': '#d8c86a', 'class': 'emissive'},
         'crab': {'color': '#7a6a4a', 'class': 'emissive', 'double_sided': True},
         'starfish': {'color': '#f08a6a', 'class': 'emissive', 'double_sided': True},
         'shoal': {'color': '#8af0e0', 'class': 'emissive', 'double_sided': True},
         'hose': {'color': '#3a6a3a'}, 'airstone': {'color': '#c8c8ff', 'class': 'emissive'}}
    n = []
    occupants = Mesh()
    contents = {
        # the front row, nearest the camera
        ('b', 0): 'ray', ('b', 1): 'shoal', ('b', 2): 'dry', ('b', 3): 'puffer', ('b', 4): 'stars',
        ('a', 0): 'moray', ('a', 1): 'crab', ('a', 2): 'octopus', ('a', 3): 'shoal2', ('a', 4): 'ray2',
    }
    floor_y = STAND + 0.012
    for name, row in ROWS.items():
        for k, (x0, z0, x1, z1) in enumerate(tank_spans(row)):
            what = contents[(name, k)]
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            n.append(box(f'glass_{name}{k}', (x0, STAND + 0.004, z0), (x1, GLASS_TOP, z1), 'glass', open=['top', 'bottom']))
            n.append(box(f'bottom_{name}{k}', (x0 + 0.01, STAND, z0 + 0.01), (x1 - 0.01, floor_y, z1 - 0.01),
                         'bottom_dry' if what == 'dry' else 'bottom', open=['bottom', 'left', 'right', 'back', 'front']))
            if what != 'dry':
                n.append(box(f'water_{name}{k}', (x0 + 0.01, WATER - 0.01, z0 + 0.01), (x1 - 0.01, WATER, z1 - 0.01), 'surface',
                             open=['bottom', 'left', 'right', 'back', 'front']))
                n.append(at({'id': f'air_{name}{k}', 'op': 'cylinder', 'radius': 0.025, 'height': 0.03, 'segments': 4,
                             'material': 'airstone'}, translate=[x1 - 0.12, floor_y + 0.02, z1 - 0.1]))
            y = floor_y + 0.03
            if what == 'ray':
                ray_shape(occupants, cx - 0.1, y + 0.02, cz, 200, 0.62, 'ray', 'ray_spot')
            elif what == 'ray2':
                ray_shape(occupants, cx, y + 0.02, cz - 0.04, 20, 0.5, 'ray', 'ray_spot')
            elif what == 'shoal' or what == 'shoal2':
                rng = np.random.default_rng(k + (name == 'a') * 10)
                for j in range(7):
                    fish(occupants, cx + rng.uniform(-0.6, 0.6), y + 0.15 + 0.03 * j, cz + rng.uniform(-0.2, 0.2),
                         15 + rng.uniform(-25, 25), 0.12, 0.05, 'shoal')
            elif what == 'moray':
                n.append(at({'id': 'pipe_hide', 'op': 'cylinder', 'radius': 0.08, 'height': 0.5, 'segments': 6,
                             'material': 'pipe_hide'}, translate=[cx + 0.35, y + 0.07, cz], rotate=[0, 0, 90]))
                pts = [(cx + 0.1, cz + 0.02), (cx - 0.15, cz + 0.12), (cx - 0.4, cz + 0.02), (cx - 0.6, cz + 0.1)]
                ws = [0.045, 0.04, 0.032, 0.012]
                for j in range(len(pts) - 1):
                    (ax, az), (bx, bz) = pts[j], pts[j + 1]
                    occupants.poly([(ax, y + 0.03, az - ws[j]), (bx, y + 0.03, bz - ws[j + 1]), (bx, y + 0.03, bz + ws[j + 1]),
                                    (ax, y + 0.03, az + ws[j])], (0, 1, 0), 'moray')
            elif what == 'octopus':
                occupants.poly([(cx + 0.11 * math.cos(math.radians(a)), y + 0.12, cz + 0.08 * math.sin(math.radians(a)))
                                for a in range(0, 360, 45)], (0, 1, 0), 'octopus')
                for j in range(4):
                    a = math.radians(30 + j * 70)
                    occupants.poly([(cx + 0.06 * math.cos(a), y + 0.1, cz + 0.06 * math.sin(a)),
                                    (cx + 0.32 * math.cos(a + 0.4), y + 0.04, cz + 0.22 * math.sin(a + 0.4)),
                                    (cx + 0.06 * math.cos(a + 0.5), y + 0.1, cz + 0.06 * math.sin(a + 0.5))], (0, 1, 0), 'octopus')
                # the lid weighted shut: an octopus gets out
                n.append(box(f'lid_{name}{k}', (x0 - 0.01, GLASS_TOP - 0.004, z0 - 0.01), (x1 + 0.01, GLASS_TOP + 0.012, z1 + 0.01),
                             'lid'))
                n.append(box(f'weight_{name}{k}', (cx - 0.12, GLASS_TOP + 0.011, cz - 0.08), (cx + 0.12, 0.996, cz + 0.08), 'weight',
                             open=['bottom']))
            elif what == 'puffer':
                n.append(at({'id': 'puffer', 'op': 'sphere', 'radius': 0.09, 'segments': 6, 'rings': 3, 'material': 'puffer'},
                            translate=[cx + 0.1, y + 0.25, cz]))
            elif what == 'crab':
                occupants.poly([(cx + 0.16 * math.cos(math.radians(a)), y + 0.02, cz + 0.14 * math.sin(math.radians(a)))
                                for a in range(-90, 91, 30)], (0, 1, 0), 'crab')
                occupants.poly([(cx - 0.01, y + 0.02, cz + 0.01), (cx - 0.3, y + 0.02, cz), (cx - 0.01, y + 0.02, cz - 0.01)],
                               (0, 1, 0), 'crab')
            elif what == 'stars':
                star(occupants, cx - 0.4, y, cz - 0.05, 0.1, 'starfish', 10)
                star(occupants, cx + 0.15, y, cz + 0.1, 0.08, 'starfish', 40)
                star(occupants, cx + 0.5, y, cz - 0.1, 0.09, 'starfish', 0)
            elif what == 'dry':
                # drained for cleaning: a hose coiled on the bottom, its end over the rim
                n.append(at({'id': 'hose_coil', 'op': 'cylinder', 'radius': 0.16, 'height': 0.035, 'segments': 8, 'caps': False,
                             'material': 'hose'}, translate=[cx - 0.1, floor_y + 0.012, cz]))
                n.append(box('hose_end', (cx + 0.05, floor_y, cz - 0.02), (cx + 0.09, GLASS_TOP + 0.02, cz + 0.02), 'hose',
                             open=['bottom']))
    n.append(occupants.node('occupants', 'ray'))
    m = prune(m, n)
    return recipe(P + 'tanks', m, n, {'bake': False}, 600)


def wwater_recipe():
    """Agent W (NOTES_W.md): the faint violet net the tanks' water throws on the floor beside each
    row, lit by a light of its own over each row."""
    ov = wateranim.Overlay(P + 'wwater')
    ov.material('net', 'w_caustic')
    for name, (x0, z0, x1, z1) in ROWS.items():
        bx = LIGHTS['uv_' + name]          # inside its ultraviolet box, as the paint's net was
        ov.floor('net', 0.03, x0 - 0.3, x1 + 0.3, max(z0 - 0.8, bx[1] + 0.05), min(z1 + 0.8, bx[3] - 0.05), nx=4, nz=1)
        for k, lx in enumerate((x0 + (x1 - x0) * 0.25, x0 + (x1 - x0) * 0.75)):
            ov.light((lx, 1.1, (z0 + z1) / 2), '#9a64ff', 0.75, 2.4, id=f'row_{name}{k}')
    return ov.recipe(ART, refine={'tolerance': 20, 'max_added': 32})


def main():
    art8, art4 = {}, {}
    for name, x0, x1, z0, z1 in R.floor_tiles(2, 2):
        art8[P + name] = paint_floor_tile(x0, x1, z0, z1)
    for name, a, b in R.back_chunks(7.0):
        art8[P + name] = paint_wall(a, b, 0.0, 2.4, R.Z1, wall_base, wall_lights(), 0.16, wall_extra)
    art4.update({P + 'section': paint_section(R.XO0, R.XO1), P + 'ripple': paint_ripple(), P + 'cabinet': paint_cabinet(),
                 P + 'log': paint_log(), P + 'rack': paint_rack()})
    for k, col in enumerate(((220, 60, 60), (60, 120, 220), (240, 190, 50))):
        art4[f'{P}tub_{k}'] = paint_tub(col=col)
    for k in range(4):
        art4[f'{P}card_{k}'] = paint_card(k)
    save_art(art8, art4, ART)
    recs = [*room_recipe(), wateranim.finish(tanks_recipe(), ART), wwater_recipe(),     # agent W: the water
            collision_recipe(G.ROOM, P + 'room_col')]
    for rec in recs:
        write_json(OUT / f'{rec["name"]}.asset.json', rec)
    print(f'texture bytes (estimate): {vram(art8, art4):,}')
    if '--no-placements' not in sys.argv:
        write_json(HERE / 'aq_quar.placements.json',
                   placements_file('aq_quar', [(P + 'room', P + 'room', P + 'room_col'), (P + 'props', P + 'props', 'none'),
                                                (P + 'tanks', P + 'tanks', 'none'),
                                                (P + 'wwater', P + 'wwater', 'none')]))     # agent W


if __name__ == '__main__':
    main()
