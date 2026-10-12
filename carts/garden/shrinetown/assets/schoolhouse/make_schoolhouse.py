#!/usr/bin/env python3
"""Writes shrine town's school (Hinata Elementary): art/school_sheet.png (+ .sheet.json),
schoolhouse.asset.json and schoolhouse_col.asset.json.

Adapted from the lab model (examples/assets/lab/schoolhouse, 1,308 triangles): there it is the
old two-storey wooden school with a clock tower to 18.9. The level needs a roof to stand on at
18.9 (spec 3.15, 6.3: the water tank, a lost ball, glide G9 north to the cemetery) and an
outside fire stair up to it, so the school is the town's 1960s concrete rebuild that kept the old
school's things: the clock tower (now the stair core, rising 3.4 over the roof to its copper
pyramid and finial), the gabled entrance porch with the glazed double doors and the
ひなた小学校 board, the round window, the pale-green sashes (now long classroom bands), the
Hinomaru on its pole, the Ninomiya Kinjiro statue and the horizontal bars (the yard's tree is
the shrine's tree_maple_small, placed beside it). Its sheet is the lab's with the two facade tiles drawn here; walls
and roofs use the town's common plaster and roof tile.

Plan (origin at the centre of the grey box's 30 x 30 footprint, x 258-288, z 56-86; front, the
yard side, toward -Z = south, so it is placed at (273, 0, 71) with yaw 0):

- classroom block x -14..10, z 4..15, five storeys of 3.72 on a 0.3 plinth: roof 18.9, parapet
  0.75 (top 19.65); its north edge at x 0 is G9's take-off, (273, 86)
- wing x -14..-6, z -12..4, four storeys: roof 15.18, parapet top 15.93; the main roof's
  parapet is 4.47 over the wing's roof: a double jump and a grab
- clock tower x -2..2, z 2.6..6.6, top 22.3 with a 0.5 m walk round the pyramid's foot, cornice
  ledge at 21.9; pyramid to 24.7, finial to 25.6
- porch x -3..3, z -0.6..2.6, eaves 4.4, ridge 6.0 (26.6 degrees: walkable)
- fire stair on the east end, x 10..13, z 4..15: five flights of 3.78 at 25 degrees in two
  lanes, landings at the south (z 4..5.3) and north (z 13.4..15) ends; the foot is at the south
  end of the inner lane, (10.8, 0, 5.3); the top landing (18.9) opens west onto the roof
  through a gap in the parapet at z 13.4..14.75
- yard: the flagpole (a pole, 9.1 m, at (6, -2)), the bars, the statue

Levels: L1 from 24 m, L2 from 60 m, culled at 300 m (it is a landmark: spec 1.3).

Run: python3 carts/garden/shrinetown/assets/schoolhouse/make_schoolhouse.py   (needs Pillow)
"""
import json
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "schoolhouse", "art", "schoolhouse_sheet")
ART = os.path.join(HERE, "art")
COMMON = "../town_alley_house_a/art/town_common.png"

BASE = 0.3
FL = 3.72                    # a storey
ROOF = BASE + 5 * FL         # 18.9
WROOF = BASE + 4 * FL        # 15.18
PH, PT = 0.75, 0.25           # parapet height and thickness
MX0, MX1, MZ0, MZ1 = -14.0, 10.0, 4.0, 15.0      # classroom block
WX0, WX1, WZ0, WZ1 = -14.0, -6.0, -12.0, 4.0     # wing
TX, TZ0, TZ1 = 2.0, 2.6, 6.6                     # tower: x -2..2
TOP = ROOF + 3.4             # 22.3
PX, PZ0, PZ1, PEAVE, PRIDGE = 3.0, -0.6, 2.6, 4.4, 6.0
# the fire stair
SX0, SXM, SX1 = 10.0, 11.5, 13.0
SZ0, SZS, SZN, SZ1 = 4.0, 5.3, 13.4, 15.0
RISE = ROOF / 5              # 3.78
SLOPE = RISE / (SZN - SZS)   # 0.467, 25 degrees
GAP_Z = (SZN, MZ1 - PT)      # the parapet's gap for the stair


# ---- art -------------------------------------------------------------------------------
GLASS = [(46, 78, 92), (58, 94, 108), (70, 108, 120), (36, 62, 76)]
FRAME, SHADE = (176, 202, 178), (122, 150, 128)
CREAM, CREAM_D, SILL = (217, 207, 185), (203, 192, 168), (176, 172, 162)


def hsh(a, b=0, c=0):
    h = (a * 374761393 + b * 668265263 + c * 1442695041 + 777) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF


def rect(d, x0, y0, x1, y1, c):
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=c)


def facade(rows, seed, curtains):
    """64 x 32: two 4 m bays of one 3.72 m storey (row 0 its top). rows: the window's first and
    last row. Pale-green sashes, four panes a bay, teal glass, a pillar between bays."""
    im = Image.new("RGB", (64, 32), CREAM)
    d = ImageDraw.Draw(im)
    r0, r1 = rows
    rect(d, 0, 0, 64, 1, CREAM_D)                     # the floor slab's line
    for bay in range(2):
        x0 = bay * 32 + 2
        x1 = x0 + 28
        rect(d, x0, r0, x1, r1, FRAME)
        rect(d, x0 - 1, r1, x1 + 1, r1 + 2, SILL)     # sill
        transom = r0 + (r1 - r0) // 3
        for p in range(4):
            px0 = x0 + 1 + p * 7
            for (ya, yb, k) in ((r0 + 1, transom, 0), (transom + 1, r1 - 1, 1)):
                g = GLASS[hsh(bay, p, seed * 10 + k) % 4]
                rect(d, px0, ya, px0 + 6, yb, g)
                if hsh(bay, p, seed * 10 + k + 5) % 3 == 0:
                    rect(d, px0 + 1, ya + 1, px0 + 3, ya + 2, (150, 190, 200))
        rect(d, x0 + 14, r0, x0 + 15, r1, SHADE)      # sashes pass at the middle
        for (b, p) in curtains:
            if b == bay:
                px0 = x0 + 1 + p * 7
                rect(d, px0, transom + 1, px0 + 3, r1 - 1, (232, 224, 200))
    return im


def draw_art():
    os.makedirs(ART, exist_ok=True)
    lab = Image.open(LAB + ".png").convert("RGBA")
    cells = json.load(open(LAB + ".sheet.json"))["cells"]
    sheet = Image.new("RGBA", (128, 192), (0, 0, 0, 0))
    sheet.paste(lab, (0, 0))
    del cells["window"], cells["dwin"]                # replaced by the facades
    cells["dwin"] = [72, 76, 24, 20]                  # kept: the stair-core windows
    cells["facade_s"] = [0, 128, 64, 32]
    cells["facade_n"] = [64, 128, 64, 32]
    sheet.paste(facade((6, 26), 1, [(1, 1)]), (0, 128))
    sheet.paste(facade((11, 24), 2, []), (64, 128))
    sheet = sheet.crop((0, 0, 128, 160))
    sheet.save(os.path.join(ART, "school_sheet.png"))
    with open(os.path.join(ART, "school_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- helpers ---------------------------------------------------------------------------
def r4(v):
    return [round(a, 4) for a in v]


def box(id, size, pos, mat, open=None, faces=None, decals=None, rot=None):
    n = {"id": id, "op": "box", "size": r4(size), "material": mat,
         "transform": {"translate": r4(pos)}}
    if rot:
        n["transform"]["rotate"] = rot
    for k, v in (("open", open), ("faces", faces), ("decals", decals)):
        if v:
            n[k] = v
    return n


def span(id, x0, x1, y0, y1, z0, z1, mat, **kw):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               mat, **kw)


def cyl(id, r, h, pos, mat, segments=6, caps=False, rot=None):
    n = {"id": id, "op": "cylinder", "radius": r, "height": round(h, 4), "segments": segments,
         "caps": caps, "material": mat, "transform": {"translate": r4(pos)}}
    if rot:
        n["transform"]["rotate"] = rot
    return n


def sphere(id, r, pos, mat, segments=6, rings=3, scale=None):
    n = {"id": id, "op": "sphere", "radius": r, "segments": segments, "rings": rings,
         "material": mat, "transform": {"translate": r4(pos)}}
    if scale:
        n["transform"]["scale"] = scale
    return n


def outward(verts, faces):
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    out = []
    for f in faces:
        a, b, d = (verts[f[0]], verts[f[1]], verts[f[2]])
        u = [b[i] - a[i] for i in range(3)]
        w = [d[i] - a[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        fc = [sum(verts[k][i] for k in f) / len(f) for i in range(3)]
        dot = sum(n[i] * (fc[i] - c[i]) for i in range(3))
        out.append(list(f) if dot > 0 else list(reversed(f)))
    return out


def prism(id, x0, x1, zy, mats):
    """A prism across x whose side outline is the points zy ((z, y), round the outline); mats:
    one per outline edge, then the -x and +x caps."""
    v = [[x0, y, z] for z, y in zy] + [[x1, y, z] for z, y in zy]
    n = len(zy)
    faces = [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)]
    faces += [list(range(n)), [n + k for k in range(n)]]
    return {"id": id, "op": "mesh", "vertices": [r4(p) for p in v], "faces": outward(v, faces),
            "face_materials": mats}


def quad(id, mat, corners):
    return {"id": id, "op": "mesh", "material": mat, "vertices": [r4(c) for c in corners],
            "faces": [[0, 1, 2, 3]]}


def facade_mat(cell, y0, y1, x_centre):
    """A facade material for a box from y0 to y1 (storeys from y0) whose bays start at x0 = a
    multiple of 4 m from x_centre: v offset so that storeys begin at whole repeats."""
    centre = (y0 + y1) / 2
    voff = round((centre - y0) / FL % 1.0, 6)
    return {"color": "#d9cfb9", "tag": "wall",
            "texture": {"sheet": "school", "cell": cell, "projection": "box",
                        "scale": [8, FL], "offset": [0, voff]}}


def floors_storeys(y0, y1):
    return round((y1 - y0) / FL)


# ---- the buildings ---------------------------------------------------------------------
def blocks(top_main=ROOF, top_wing=WROOF, detail=True):
    n = [span("block", MX0, MX1, BASE, top_main, MZ0, MZ1, "wall", open=["bottom"],
              faces={"back": "facade_s", "front": "facade_n", "top": "roof"}),
         span("wing", WX0, WX1, BASE, top_wing, WZ0, WZ1, "wall", open=["bottom", "front"],
              faces={"right": "facade_sw", "left": "facade_nw", "back": "facade_nw", "top": "roof"})]
    if detail:
        n += [span("plinth", MX0 - 0.1, MX1 + 0.1, 0, BASE + 0.02, MZ0 - 0.1, MZ1 + 0.1, "stone",
                   open=["bottom"]),
              span("wing_plinth", WX0 - 0.1, WX1 + 0.1, 0, BASE + 0.02, WZ0 - 0.1, MZ0 - 0.1,
                   "stone", open=["bottom", "front"])]
    return n


def parapets():
    y0, y1 = ROOF, ROOF + PH
    w0, w1 = WROOF, WROOF + PH
    cap = {"top": "coping"}
    return [
        span("par_n", MX0, MX1, y0, y1, MZ1 - PT, MZ1, "wall", open=["bottom"], faces=cap),
        span("par_s", MX0, MX1, y0, y1, MZ0, MZ0 + PT, "wall", open=["bottom"], faces=cap),
        span("par_w", MX0, MX0 + PT, y0, y1, MZ0 + PT, MZ1 - PT, "wall",
             open=["bottom", "back", "front"], faces=cap),
        span("par_e", MX1 - PT, MX1, y0, y1, MZ0 + PT, GAP_Z[0], "wall", open=["bottom", "back"],
             faces=cap),
        span("wpar_s", WX0, WX1, w0, w1, WZ0, WZ0 + PT, "wall", open=["bottom"], faces=cap),
        span("wpar_w", WX0, WX0 + PT, w0, w1, WZ0 + PT, WZ1, "wall", open=["bottom", "back", "front"],
             faces=cap),
        span("wpar_e", WX1 - PT, WX1, w0, w1, WZ0 + PT, WZ1, "wall", open=["bottom", "back", "front"],
             faces=cap),
    ]


def tower(detail=True):
    h = TOP
    cy = h / 2
    tz = (TZ0 + TZ1) / 2
    decals = [{"id": "clock_s", "face": "back", "material": "clock", "size": [1.9, 1.9],
               "at": [0, 20.3 - cy]}]
    if detail:
        decals += [{"id": "rwin", "face": "back", "material": "rwin", "size": [1.2, 1.2],
                    "at": [0, 7.6 - cy]},
                   {"id": "win_3", "face": "back", "material": "dwin", "size": [1.2, 1.0],
                    "at": [0, BASE + 3 * FL + 1.6 - cy]},
                   {"id": "clock_n", "face": "front", "material": "clock", "size": [1.9, 1.9],
                    "at": [0, 20.3 - cy]},
                   ]
    n = [box("tower", [2 * TX, h, TZ1 - TZ0], [0, cy, tz], "wall", open=["bottom"],
             faces={"top": "coping"}, decals=decals),
         {"id": "pyramid", "op": "cone", "radius": round(1.5 * math.sqrt(2), 4), "height": 2.4,
          "segments": 4, "caps": False, "material": "copper",
          "transform": {"rotate": [0, 45, 0], "translate": [0, TOP - 0.01 + 1.2, tz]}}]
    if detail:
        n += [span("cornice", -TX - 0.2, TX + 0.2, TOP - 0.7, TOP - 0.4, TZ0 - 0.2, TZ1 + 0.2,
                   "coping"),
              cyl("finial_rod", 0.05, 1.0, [0, TOP + 2.39 + 0.5, tz], "iron", segments=4),
              sphere("finial", 0.16, [0, TOP + 2.39 + 1.0, tz], "gold", segments=4)]
    return n


def porch(detail=True):
    zf = PZ0
    cy = PEAVE / 2
    decals = None
    if detail:
        decals = [{"id": "door", "face": "back", "material": "door", "size": [3.0, 2.6],
                   "at": [0, 1.4 - cy]},
                  {"id": "plaque", "face": "back", "material": "plaque", "size": [3.6, 0.56],
                   "at": [0, 3.55 - cy]}]
    ex = PX + 0.4
    z0, z1 = zf - 0.45, PZ1
    v = [[-ex, PEAVE, z0], [0, PRIDGE, z0], [ex, PEAVE, z0],
         [-ex, PEAVE, z1], [0, PRIDGE, z1], [ex, PEAVE, z1]]
    n = [span("porch", -PX, PX, 0, PEAVE, PZ0, PZ1, "wall", open=["bottom", "top", "front"],
              decals=decals),
         {"id": "porch_roof", "op": "mesh", "material": "kawara", "double_sided": False,
          "vertices": [r4(p) for p in v], "faces": [[0, 3, 4, 1], [1, 4, 5, 2]]}]
    n[-1].pop("double_sided")
    # the gable's triangle over the porch front
    n.append({"id": "pediment", "op": "mesh", "material": "wall",
              "vertices": [r4(p) for p in [[-PX, PEAVE, zf], [0, PRIDGE - 0.12, zf], [PX, PEAVE, zf]]],
              "faces": [[0, 1, 2]]})
    if detail:
        for s in (-1, 1):
            n.append(span(f"lamp_{'l' if s < 0 else 'r'}", s * 2.6 - 0.14, s * 2.6 + 0.14, 3.0, 3.36,
                          zf - 0.3, zf - 0.02, "lamp"))
    return n


# ---- the fire stair --------------------------------------------------------------------
def flights():
    """[(k, lane x0, x1, z_low, z_high, y_low, y_high)] for the five flights."""
    out = []
    for k in range(1, 6):
        if k % 2:
            x0, x1, zl, zh = SX0 + 0.05, SXM - 0.02, SZS, SZN
        else:
            x0, x1, zl, zh = SXM + 0.02, SX1 - 0.05, SZN, SZS
        out.append((k, x0, x1, zl, zh, (k - 1) * RISE, k * RISE))
    return out


def flight_outline(zl, zh, yl, yh, t):
    if yl - t < 0:
        dz = (zh - zl) / abs(zh - zl)
        return [(zl, yl), (zh, yh), (zh, yh - t), (zl + dz * t / SLOPE, 0.0)]
    return [(zl, yl), (zh, yh), (zh, yh - t), (zl, yl - t)]


def landings():
    """[(id, z0, z1, y)]: north landings at odd heights, south at even, the top one at 18.9."""
    out = []
    for k in range(1, 6):
        y = k * RISE
        if k % 2:
            out.append((f"land_{k}", SZN - 0.03, SZ1, y))
        else:
            out.append((f"land_{k}", SZ0, SZS + 0.03, y))
    return out


def fire_stair(detail=True):
    n = []
    t = 0.25
    for k, x0, x1, zl, zh, yl, yh in flights():
        n.append(prism(f"flight_{k}", x0, x1, flight_outline(zl, zh, yl, yh, t),
                       ["tread", "steel", "steel", "steel", "steel", "steel"]))
    for id, z0, z1, y in landings():
        n.append(span(id, SX0, SX1, y - 0.2, y, z0, z1, "steel", open=["left"],
                      faces={"top": "tread"}))
    if not detail:
        return n
    # railings: bars over each flight's open side, each landing's outer side and end
    r = 1.0
    for k, x0, x1, zl, zh, yl, yh in flights():
        x = (SXM - 0.03) if k % 2 else (SX1 - 0.08)
        n.append(quad(f"rail_{k}", "bars", [[x, yh + r, zh], [x, yl + r, zl], [x, yl, zl], [x, yh, zh]]))
    for id, z0, z1, y in landings():
        n.append(quad(f"{id}_rail", "bars", [[SX1 - 0.12, y + r, z1], [SX1 - 0.12, y + r, z0],
                                              [SX1 - 0.12, y, z0], [SX1 - 0.12, y, z1]]))
        ze = (z1 - 0.2) if z0 > 10 else (z0 + 0.2)
        n.append(quad(f"{id}_end", "bars", [[SX0 + 0.05, y + r, ze], [SX1 - 0.08, y + r, ze],
                                             [SX1 - 0.08, y, ze], [SX0 + 0.05, y, ze]]))
    for i, (x, z) in enumerate(((SXM, SZ0 + 0.1), (SX1 - 0.1, SZ0 + 0.1),
                                (SXM, SZ1 - 0.1), (SX1 - 0.1, SZ1 - 0.1))):
        n.append(span(f"post_{i}", x - 0.06, x + 0.06, 0, ROOF + 1.0, z - 0.06, z + 0.06, "steel_ds",
                      open=["top", "bottom"]))
    return n


# ---- on the roof and in the yard -------------------------------------------------------
def roof_things(detail=True):
    n = [span("tank_stand", 5.2, 7.8, ROOF - 0.02, ROOF + 1.0, 8.2, 10.3, "steel",
              open=["top", "bottom"]),
         span("tank", 4.9, 8.1, ROOF + 1.0, ROOF + 3.0, 7.9, 10.6, "tank", open=["bottom"])]
    if detail:
        n.append(sphere("ball", 0.11, [2.6, ROOF + 0.11, 12.4], "ball", segments=5, rings=3))
    return n


def yard(detail=True):
    n = [cyl("flagpole", 0.07, 9.0, [6.0, 4.5, -2.0], "iron", segments=5),
         quad("flag", "flag", [[4.0, 8.85, -2.0], [5.95, 8.85, -2.0], [5.95, 7.55, -2.0], [4.0, 7.55, -2.0]])]
    # (the cherry tree is a placement of its own now, the shrine's tree_maple_small, west of the
    # paved way to the fire stair: place/east.py; here it was two flat spheres on the way)
    if not detail:
        return n
    n += [sphere("pole_ball", 0.15, [6.0, 9.1, -2.0], "gold", segments=4)]
    # the woodcutter boy reading as he walks
    n += [span("statue_plinth", -5.05, -4.15, 0, 0.5, -3.45, -2.55, "stone", open=["bottom"]),
          cyl("statue_body", 0.2, 0.62, [-4.6, 0.8, -3.0], "bronze", segments=6, caps=True),
          sphere("statue_head", 0.14, [-4.6, 1.25, -3.0], "bronze", segments=4),
          box("statue_wood", [0.55, 0.14, 0.16], [-4.6, 0.95, -2.82], "bronze", rot=[-10, 0, 0])]
    # the horizontal bars, two heights
    for i, (x, h) in enumerate(((1.6, 1.3), (3.8, 1.3), (6.0, 1.0))):
        n.append(cyl(f"bar_post_{i}", 0.04, h, [x, h / 2, -12.0], "iron", segments=4))
    n += [cyl("bar_a", 0.035, 2.2, [2.7, 1.25, -12.0], "rail", segments=4, rot=[0, 0, 90]),
          cyl("bar_b", 0.035, 2.2, [4.9, 0.95, -12.0], "rail", segments=4, rot=[0, 0, 90])]
    return n


# ---- materials -------------------------------------------------------------------------
def cell(name, color="#ffffff", **kw):
    m = {"color": color, "texture": {"sheet": "school", "cell": name, "projection": "fit"}}
    m.update(kw)
    return m


MATERIALS = {
    "wall": {"color": "#d9cfb9", "tag": "wall", "texture": {"sheet": "common", "cell": "plaster",
                                                            "projection": "box", "scale": [4, 4]}},
    "roof": {"color": "#b0aca2", "tag": "roof", "texture": {"sheet": "common", "cell": "plaster_grey",
                                                            "projection": "box", "scale": [4, 4]}},
    "kawara": {"color": "#565c64", "tag": "roof", "texture": {"sheet": "common", "cell": "kawara",
                                                              "projection": "box", "scale": [2, 2],
                                                              "rotate": 90}},
    "facade_s": facade_mat("facade_s", BASE, ROOF, 0),
    "facade_n": facade_mat("facade_n", BASE, ROOF, 0),
    "facade_sw": facade_mat("facade_s", BASE, WROOF, 0),
    "facade_nw": facade_mat("facade_n", BASE, WROOF, 0),
    "bars": {"color": "#6a7a74", "double_sided": True, "texture": {
        "texels": ["11111111", "11001100", "11001100", "11001100", "11001100", "11001100",
                   "11001100", "11001100"],
        "colors": ["#000000", "#6a7a74"], "clear": "#000000", "projection": "box",
        "scale": [0.5, 0.5]}},
    "tank": {"color": "#c8ccc4", "texture": {"pattern": "tile", "colors": ["#c8ccc4", "#9aa098"],
                                             "params": {"count": 2, "grout": 1}, "size": 16,
                                             "projection": "box", "scale": [2, 2]}},
    "coping": {"color": "#b0aca2", "palette": True},
    "stone": {"color": "#b0aca2", "palette": True},
    "steel": {"color": "#6a7a74", "palette": True},
    "tread": {"color": "#4e5a56", "palette": True, "tag": "stairs"},
    "steel_ds": {"color": "#6a7a74", "palette": True, "double_sided": True},
    "copper": {"color": "#7a8a70", "palette": True, "tag": "roof"},
    "iron": {"color": "#6a7a74", "palette": True},
    "gold": {"color": "#d8b048", "palette": True},
    "bronze": {"color": "#5a4a3e", "palette": True},
    "rail": {"color": "#6a7a74", "palette": True},
    "ball": {"color": "#c8542e", "palette": True, "smooth": True},
    "lamp": {"color": "#f4d27a", "class": "emissive", "tag": "lantern"},
    "door": cell("door", "#5a3e2c", tag="door"),
    "plaque": cell("plaque", "#c4a070"),
    "clock": cell("clock", "#f2ecd6"),
    "louver": cell("louver", "#28221f"),
    "rwin": cell("rwin", "#466c78"),
    "dwin": cell("dwin", "#466c78"),
    "flag": cell("flag", "#f6f4ee", double_sided=True),
}


def level0():
    return (blocks() + parapets() + tower() + porch() + fire_stair() + roof_things() + yard())


def level1():
    # the fire stair as flat flights and landings, seen from both sides, and its outer bars
    stair = []
    for k, x0, x1, zl, zh, yl, yh in flights():
        stair.append(quad(f"flight_{k}", "steel_ds", [[x0, yh, zh], [x1, yh, zh], [x1, yl, zl], [x0, yl, zl]]))
    for id, z0, z1, y in landings():
        stair.append(quad(id, "steel_ds", [[SX0 + 0.05, y, z1], [SX1, y, z1], [SX1, y, z0], [SX0 + 0.05, y, z0]]))
    stair.append(quad("cage", "bars", [[SX1, ROOF + 1.0, SZ0], [SX1, ROOF + 1.0, SZ1], [SX1, 0, SZ1], [SX1, 0, SZ0]]))
    return (blocks(detail=False) + tower(False) + porch(False) + stair
            + roof_things(False) + yard(False))


def level2():
    return [span("block", MX0, SX1, BASE, ROOF + PH, MZ0, MZ1, "facade_s", open=["bottom"],
                 faces={"top": "coping"}),
            span("wing", WX0, WX1, BASE, WROOF + PH, WZ0, WZ1, "facade_sw",
                 open=["bottom", "front"], faces={"top": "coping"}),
            span("tower", -TX, TX, ROOF + PH - 0.02, TOP, TZ0, TZ1, "wall", open=["bottom", "top"]),
            {"id": "pyramid", "op": "cone", "radius": round(TX * math.sqrt(2), 4), "height": 2.4,
             "segments": 4, "caps": False, "material": "copper",
             "transform": {"rotate": [0, 45, 0], "translate": [0, TOP - 0.01 + 1.2, (TZ0 + TZ1) / 2]}}]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "schoolhouse",
        "budget": {"vertices": 900, "triangles": 800},
        "sheets": {"school": {"image": "art/school_sheet.png"}, "common": {"image": COMMON}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 300, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None):
    return span(id, x0, x1, y0, y1, z0, z1, "solid", open=open)


def collision():
    tz = (TZ0 + TZ1) / 2
    # the classroom block in two, split where the stair's top landing starts, so the roof's east
    # edge meets the landing edge to edge (no T-junction)
    lz = landings()[-1][1]
    n = [solid("block", MX0, MX1, 0, ROOF, MZ0, lz, open=["bottom", "front"]),
         solid("block_n", MX0, MX1, 0, ROOF, lz, MZ1, open=["bottom", "back"]),
         solid("wing", WX0, WX1, 0, WROOF, WZ0, MZ0, open=["bottom", "front"])]
    # parapets: walls 0.25 thick to stand on (the roof's edges)
    y0, y1, w0, w1 = ROOF, ROOF + PH, WROOF, WROOF + PH
    n += [solid("par_n", MX0, MX1, y0, y1, MZ1 - PT, MZ1, open=["bottom"]),
          solid("par_s", MX0, MX1, y0, y1, MZ0, MZ0 + PT, open=["bottom"]),
          solid("par_w", MX0, MX0 + PT, y0, y1, MZ0 + PT, MZ1 - PT, open=["bottom", "back", "front"]),
          solid("par_e", MX1 - PT, MX1, y0, y1, MZ0 + PT, GAP_Z[0], open=["bottom", "back"]),
          solid("wpar_s", WX0, WX1, w0, w1, WZ0, WZ0 + PT, open=["bottom"]),
          solid("wpar_w", WX0, WX0 + PT, w0, w1, WZ0 + PT, MZ0, open=["bottom", "back", "front"]),
          solid("wpar_e", WX1 - PT, WX1, w0, w1, WZ0 + PT, MZ0, open=["bottom", "back", "front"])]
    # the tower (its walk at 22.3 round the pyramid; the cornice a ledge at 21.9) and pyramid
    n += [solid("tower", -TX, TX, ROOF - 0.02, TOP, TZ0, TZ1, open=["bottom"]),
          solid("tower_base", -TX, TX, 0, ROOF - 0.02, TZ0, MZ0, open=["bottom", "top", "front"]),
          solid("cornice", -TX - 0.2, TX + 0.2, TOP - 0.7, TOP - 0.4, TZ0 - 0.2, TZ1 + 0.2),
          {"id": "pyramid", "op": "cone", "radius": round(1.5 * math.sqrt(2), 4), "height": 2.4,
           "segments": 4, "caps": False, "material": "solid",
           "transform": {"rotate": [0, 45, 0], "translate": [0, TOP - 0.01 + 1.2, tz]}}]
    # the porch and its gable (26.6 degrees)
    ex = PX + 0.4
    z0, z1 = PZ0 - 0.45, PZ1 - 0.02
    v = [[-ex, PEAVE, z0], [0, PRIDGE, z0], [ex, PEAVE, z0], [-ex, PEAVE, z1], [0, PRIDGE, z1],
         [ex, PEAVE, z1]]
    n += [solid("porch", -PX, PX, 0, PEAVE, PZ0, TZ0, open=["bottom", "top", "front"]),
          {"id": "porch_roof", "op": "mesh", "material": "solid", "vertices": v,
           "faces": [[0, 3, 4, 1], [1, 4, 5, 2], [0, 1, 2], [5, 4, 3]]}]
    # the fire stair: flights, landings, the outer railings as walls 1.0 over them
    # (the outer wall is x SX1-0.25..SX1; flights and landings stop short of it or cross into it,
    # so no two faces lie in one plane)
    WI = SX1 - 0.25
    for k, x0, x1, zl, zh, yl, yh in flights():
        x1 = min(x1, WI + 0.1)
        n.append(prism(f"flight_{k}", x0, x1, flight_outline(zl, zh, yl, yh, 0.25), ["solid"] * 6))
        if k % 2 == 0:
            dz = 0.02 if zh > zl else -0.02
            n.append(prism(f"flight_{k}_wall", WI, SX1,
                           [(zl + dz, yl + 1.0), (zh - dz, yh + 1.0), (zh - dz, yh - 0.15),
                            (zl + dz, yl - 0.15)], ["solid"] * 6))
    for id, z0, z1, y in landings():
        n.append(solid(id, SX0, WI, y - 0.2, y, z0, z1, open=["left", "right"]))
        n.append(solid(f"{id}_wall", WI + 0.03, SX1 - 0.03, y - 0.2, y + 1.0, z0, z1))
        ze0, ze1 = (z1 - 0.25, z1 - 0.05) if z0 > 10 else (z0 + 0.05, z0 + 0.25)
        n.append(solid(f"{id}_end", SX0 + 0.05, WI + 0.08, y, y + 0.97, ze0, ze1, open=["bottom"]))
    # roof and yard
    n += [solid("tank", 4.9, 8.1, ROOF - 0.02, ROOF + 3.0, 7.9, 10.6, open=["bottom"]),
          # the horizontal bars (posts and bar, two heights): walls, not walked through (alpha
          # review r12 #9); their tops are floors to stand on
          solid("bars_high", 1.56, 3.84, 0, 1.29, -12.04, -11.96, open=["bottom"]),
          solid("bars_low", 3.84, 6.04, 0, 0.99, -12.04, -11.96, open=["bottom", "left"]),
          solid("statue", -5.05, -4.15, 0, 1.4, -3.45, -2.55, open=["bottom"])]
    return {
        "format": "mei-asset", "version": 1, "name": "schoolhouse_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": {"solid": {"color": "#c8c4b8"}},
        "nodes": n,
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("schoolhouse.asset.json", recipe())
    write("schoolhouse_col.asset.json", collision())
