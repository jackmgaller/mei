#!/usr/bin/env python3
"""Writes the shrine town's danchi: art/danchi_sheet.png (+ .sheet.json), danchi.asset.json and
danchi_col.asset.json.

Adapted from the lab model (examples/assets/lab/danchi, 1,064 triangles, five storeys), whose
sheet it reads for the doors, windows, number, stains, laundry, fan and antenna. The town's danchi
is seven storeys (roof 18.8, spec 3.1), with an outside stair on its back to the roof and a water
tank on the roof (top 20.8, red coin 4). The balcony doors and windows are a repeating facade
texture instead of separate quads, which is most of the cut.

Run: python3 carts/garden/shrinetown/assets/danchi/make_danchi.py   (needs Pillow)
"""
import json
import os
import random

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "danchi", "art", "danchi_sheet.png")
LAB_CELLS = {
    "door_a": (0, 0, 32, 20), "door_b": (32, 0, 32, 20), "door_c": (0, 20, 32, 20),
    "door_d": (32, 20, 32, 20), "window": (64, 0, 16, 12), "kitchen": (80, 0, 16, 16),
    "number": (0, 40, 32, 48), "laundry": (32, 40, 48, 16), "fan": (80, 40, 16, 12),
    "antenna": (96, 40, 32, 16), "sudare": (128, 40, 16, 24), "stains": (0, 96, 32, 32),
}

# ---- dimensions (metres) ---------------------------------------------------------------
STOREY = 18.8 / 7          # 2.6857: seven storeys, roof 18.8
ROOF = 18.8
PARAPET = 0.3              # low enough to step over (0.32)
W = 16.0                   # body width (x)
ZF, ZB = -5.1, 3.7         # body front (balconies, -Z) and back (stair) faces
BAL = 1.3                  # balcony depth
RAIL = 1.05
T_X0, T_X1 = 2.6, 8.0      # stair tower along the back, east end
T_Z1 = 6.6
T_BOT = 2.52               # tower cage starts above the ground floor (open underneath)
T_TOP = ROOF + 1.1
LAND = 1.357               # landing length; flight run is 2 * the rise
FLIGHTS = 14
RISE = ROOF / FLIGHTS      # 1.343
RUN = 2 * RISE             # 26.57 degrees

WALL = "#ddd4c0"
ENDWALL = ["#d4c8ae", "#c4b698", "#e0d6c0"]


# ---- art -------------------------------------------------------------------------------
def cell(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def speckle(img, box, colors, density, seed):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=colors[0])
    for y in range(y0, y1):
        for x in range(x0, x1):
            if rnd.random() < density:
                d.point((x, y), fill=colors[1 + rnd.randrange(len(colors) - 1)])


def draw_facade(src):
    """128 x 64: 16 m across (two units) and four storeys (16 texels each); balcony side."""
    img = Image.new("RGBA", (128, 64))
    speckle(img, (0, 0, 128, 64), [WALL, "#d2c8b2", "#e6dece"], 0.10, 3)
    d = ImageDraw.Draw(img)
    doors = [["door_c", "door_b"], ["door_a", "door_d"], ["door_d", "door_c"],
             ["door_b", "door_a"]]
    for s in range(4):
        top = 16 * s
        d.line([0, top, 127, top], fill="#bdb29c")          # slab shadow under the floor above
        for u in range(2):
            left = 64 * u
            dc = cell(src, doors[s][u]).resize((26, 12), Image.NEAREST)
            wc = cell(src, "window").resize((11, 6), Image.NEAREST)
            if u == 0:   # west unit: door, then window toward the middle
                img.paste(dc, (left + 10, top + 4))
                img.paste(wc, (left + 43, top + 5))
            else:        # east unit, mirrored
                img.paste(dc, (left + 28, top + 4))
                img.paste(wc, (left + 10, top + 5))
        d.line([63, top, 63, top + 15], fill="#cabfa8")
    return img


def draw_back(src):
    """64 x 32: 8 m (one unit) and two storeys of the back wall: kitchen and bath windows."""
    img = Image.new("RGBA", (64, 32))
    speckle(img, (0, 0, 64, 32), [WALL, "#d2c8b2", "#e6dece"], 0.10, 5)
    d = ImageDraw.Draw(img)
    k = cell(src, "kitchen").resize((9, 6), Image.NEAREST)
    for top in (0, 16):
        d.line([0, top, 63, top], fill="#bdb29c")
        img.paste(k, (10, top + 2))
        img.paste(k, (32, top + 2))
        d.rectangle([48, top + 3, 53, top + 5], fill="#9aa4aa")     # bathroom window
        d.rectangle([49, top + 4, 52, top + 4], fill="#c8d2d8")
        d.rectangle([24, top + 5, 26, top + 5], fill="#b8b0a0")     # vent
    return img


def draw_endmark(src):
    """64 x 72: the end wall's upper part: rain stains along the top, the block number."""
    img = Image.new("RGBA", (64, 72))
    speckle(img, (0, 0, 64, 72), ENDWALL, 0.12, 7)
    st = cell(src, "stains")
    st = st.resize((64, 22), Image.NEAREST)
    img.alpha_composite(st, (0, 0))
    num = cell(src, "number").resize((32, 48), Image.NEAREST)
    img.alpha_composite(num, (16, 22))
    return img


def draw_futon(color, check):
    img = Image.new("RGBA", (16, 12), color)
    d = ImageDraw.Draw(img)
    for y in range(0, 12, 4):
        for x in range(0, 16, 4):
            if (x // 4 + y // 4) % 2 == 0:
                d.rectangle([x, y, x + 1, y + 1], fill=check)
    d.line([0, 0, 15, 0], fill=check)
    return img


def draw_tank():
    img = Image.new("RGBA", (16, 16), "#8aa8bc")
    d = ImageDraw.Draw(img)
    for k in (0, 5, 10, 15):
        d.line([k, 0, k, 15], fill="#6a8aa0")
        d.line([0, k, 15, k], fill="#6a8aa0")
    for x in (2, 7, 12):
        for y in (2, 7, 12):
            d.point((x, y), fill="#a8c0d0")
    return img


def draw_bike(frame):
    """32 x 20 side view of a mamachari, holes around it."""
    img = Image.new("RGBA", (32, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for cx in (6, 25):
        d.ellipse([cx - 6, 7, cx + 6, 19], outline="#2a2a2e")
        d.point((cx, 13), fill="#9a9ea4")
    d.line([6, 13, 13, 13, 22, 6, 13, 13], fill=frame)       # chain stay, down tube
    d.line([12, 5, 13, 13], fill=frame)                      # seat tube
    d.line([12, 7, 22, 7], fill=frame)
    d.line([22, 4, 25, 13], fill=frame)                      # fork
    d.rectangle([10, 3, 14, 4], fill="#2a2a2e")              # saddle
    d.line([20, 3, 24, 3], fill="#9a9ea4")                   # bars
    d.rectangle([24, 5, 29, 9], outline="#9a9ea4")           # basket
    return img


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    cells = {}
    sheet = Image.new("RGBA", (256, 160), (0, 0, 0, 0))

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("facade", draw_facade(src), 0, 0)
    put("back", draw_back(src), 128, 0)
    put("endmark", draw_endmark(src), 0, 64)
    put("laundry", cell(src, "laundry"), 64, 64)
    put("fan", cell(src, "fan"), 112, 64)
    put("antenna", cell(src, "antenna"), 128, 64)
    put("sudare", cell(src, "sudare"), 160, 64)
    put("futon_a", draw_futon("#f0a8b8", "#fbf0f0"), 176, 64)
    put("futon_b", draw_futon("#8ab0d8", "#e8f0f8"), 192, 64)
    put("tank", draw_tank(), 208, 64)
    put("bike_a", draw_bike("#c8ccd0"), 64, 88)
    put("bike_b", draw_bike("#c04a3a"), 96, 88)
    put("bike_c", draw_bike("#3a6ab0"), 128, 88)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "danchi_sheet.png"))
    with open(os.path.join(HERE, "art", "danchi_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v, 4)


def box(id, size, at, material, open=None, faces=None, decals=None, rotate=None):
    n = {"id": id, "op": "box", "size": [r(s) for s in size], "material": material}
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    t = {"translate": [r(a) for a in at]}
    if rotate:
        t["rotate"] = rotate
    n["transform"] = t
    return n


def quad(id, material, pts, uvs=None):
    """A quad, corners clockwise as seen from the side it faces."""
    n = {"id": id, "op": "mesh", "material": material,
         "vertices": [[r(c) for c in p] for p in pts], "faces": [[0, 1, 2, 3]]}
    if uvs:
        n["uvs"] = uvs
    return n


def zquad(id, material, x0, x1, y0, y1, z, facing=-1, uvs=None):
    """A vertical quad in the plane z, seen from -Z (facing -1) or +Z (facing +1)."""
    if facing < 0:
        pts = [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]]
    else:
        pts = [[x1, y1, z], [x0, y1, z], [x0, y0, z], [x1, y0, z]]
    return quad(id, material, pts, uvs)


def xquad(id, material, z0, z1, y0, y1, x, facing=1, uvs=None):
    """A vertical quad in the plane x, seen from +X (facing 1) or -X."""
    if facing > 0:
        pts = [[x, y1, z0], [x, y1, z1], [x, y0, z1], [x, y0, z0]]
    else:
        pts = [[x, y1, z1], [x, y1, z0], [x, y0, z0], [x, y0, z1]]
    return quad(id, material, pts, uvs)


def rail_uvs(length):
    """Hand UVs for a rail quad (corners top-left first): one repeat 0.5 m across, the rail's
    full height down."""
    u = r(length / 0.5)
    return [[0, 0], [u, 0], [u, 1], [0, 1]]


def yquad(id, material, x0, x1, z0, z1, y, up=True):
    if up:
        pts = [[x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0]]
    else:
        pts = [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]
    return quad(id, material, pts)


def cyl(id, radius, height, at, material, segments=4, caps=False, rotate=None):
    n = {"id": id, "op": "cylinder", "radius": radius, "height": r(height), "segments": segments,
         "material": material}
    if not caps:
        n["caps"] = False
    t = {"translate": [r(a) for a in at]}
    if rotate:
        t["rotate"] = rotate
    n["transform"] = t
    return n


def frac(v):
    return r(v - int(v // 1))


# ---- materials -------------------------------------------------------------------------
BODY_YC = (ROOF + PARAPET) / 2
FACADE_V = 4 * STOREY
TOWER_YC = (T_BOT + T_TOP) / 2


def sheet(cellname, **extra):
    t = {"sheet": "danchi", "cell": cellname, "projection": "fit"}
    t.update(extra)
    return t


STAIR_TEX = ["1111" * 2] + ["0000" * 2] * 8 + ["2222" * 2] + ["3333" * 2] * 5 + ["4444" * 2]
STAIR_COLORS = ["#000000", "#9a958a", "#c8c4b8", "#d4c8ae", "#b8ae98"]

MATERIALS = {
    "facade": {"color": WALL, "tag": "wall", "texture": {
        "sheet": "danchi", "cell": "facade", "projection": "box",   # 4-bit (TEXTURES.md)
        "scale": [W, r(FACADE_V)], "offset": [0.5, frac(-BODY_YC / FACADE_V)]}},
    "back": {"color": WALL, "tag": "wall", "texture": {
        "sheet": "danchi", "cell": "back", "projection": "box",
        "scale": [8.0, r(2 * STOREY)], "offset": [0.5, frac(-BODY_YC / (2 * STOREY))]}},
    "endwall": {"color": ENDWALL[0], "tag": "wall", "texture": {
        "pattern": "speckle", "colors": ENDWALL, "params": {"density": 0.12},
        "projection": "box", "scale": [2.0, 2.0]}},
    "endmark": {"color": ENDWALL[0], "tag": "wall", "texture": sheet("endmark")},
    "roof": {"color": "#7e8084", "tag": "roof", "texture": {
        "pattern": "speckle", "colors": ["#7e8084", "#6e7074", "#8c8e90"],
        "params": {"density": 0.2}, "projection": "planar", "axis": "y", "scale": [2.0, 2.0]}},
    "coping": {"color": "#c8c4b8", "palette": True},
    "slab": {"color": "#cfc6b2", "palette": True, "tag": "floor"},
    "rail": {"color": "#6f9486", "double_sided": True, "texture": {
        "texels": ["11111111", "10001000", "10001000", "10001000", "10001000", "10001000",
                   "10001000", "22222222", "33333333", "33333333", "33333333", "33333333",
                   "33333333", "33333333", "33333333", "22222222"],
        "colors": ["#000000", "#5a7a6e", "#4e6c60", "#7fa496"], "clear": "#000000",
        "projection": "box", "scale": [0.5, RAIL]}},
    "partition": {"color": "#a8b8b0", "palette": True, "double_sided": True},
    "stair_wall": {"color": "#d4c8ae", "double_sided": True, "texture": {
        "texels": STAIR_TEX, "colors": STAIR_COLORS, "clear": "#000000", "projection": "box",
        "scale": [2.0, r(STOREY)], "offset": [0.0, frac(-TOWER_YC / STOREY)]}},
    "stair": {"color": "#8e887c", "palette": True, "double_sided": True, "tag": "floor"},
    "hedge": {"color": "#3c5a34", "texture": {
        "pattern": "speckle", "colors": ["#3c5a34", "#2e4a2e", "#4f6a3a"],
        "params": {"density": 0.4}, "projection": "box", "scale": [1.0, 1.0]}},
    "tank": {"color": "#8aa8bc", "tag": "roof", "texture": sheet("tank")},
    "steel": {"color": "#5a5e66", "palette": True},
    "ac": {"color": "#e2dcc8", "palette": True},
    "fan": {"color": "#e2dcc8", "texture": sheet("fan")},
    "laundry": {"color": "#f4f4f0", "double_sided": True, "texture": sheet("laundry")},
    "futon_a": {"color": "#f0a8b8", "double_sided": True, "texture": sheet("futon_a")},
    "futon_b": {"color": "#8ab0d8", "double_sided": True, "texture": sheet("futon_b")},
    "sudare": {"color": "#b08a5e", "double_sided": True, "texture": sheet("sudare")},
    "antenna": {"color": "#c0c4c8", "double_sided": True, "texture": sheet("antenna")},
    "dish": {"color": "#eceae4", "palette": True, "double_sided": True},
    "shelter": {"color": "#8aa8bc", "palette": True, "double_sided": True},
    "bike_a": {"color": "#c8ccd0", "double_sided": True, "texture": sheet("bike_a")},
    "bike_b": {"color": "#c04a3a", "double_sided": True, "texture": sheet("bike_b")},
    "bike_c": {"color": "#3a6ab0", "double_sided": True, "texture": sheet("bike_c")},
}

# Lit windows: the facade is one repeating texture, so a lit room is a card laid 4 cm over its
# drawn door or window (emissive, tagged window). Three emissive colours, shared by the three
# drawings: the sash, a lit curtain and a warm lit room.
LIT = ["#5e646c", "#f6dc9a", "#e0a056"]
MATERIALS.update({
    # balcony door: two glass leaves, curtains drawn back to the sides
    "lit_door": {"color": LIT[1], "class": "emissive", "tag": "window", "texture": {
        "texels": ["0000000000000000"] + ["0221111001111220"] * 4 + ["0211111001111120"] * 5
                  + ["0000000000000000"],
        "colors": LIT, "projection": "fit"}},
    # balcony door, one leaf's curtain closed, lit through
    "lit_door_b": {"color": LIT[1], "class": "emissive", "tag": "window", "texture": {
        "texels": ["0000000000000000"] + ["0111111002222220"] * 4 + ["0111111002222220"] * 5
                  + ["0000000000000000"],
        "colors": LIT, "projection": "fit"}},
    # small window: two sashes, a curtain half across
    "lit_win": {"color": LIT[1], "class": "emissive", "tag": "window", "texture": {
        "texels": ["00000000", "02211110", "02211110", "02111110", "02111110", "00000000"],
        "colors": LIT, "projection": "fit"}},
})


# ---- level 0 ---------------------------------------------------------------------------
def body(top_open=True, end_decals=True):
    zc = (ZF + ZB) / 2
    h = ROOF + PARAPET
    deco = []
    if end_decals:
        # number and stains over the upper end walls; at = [right, up] from the face centre
        for side in ("left", "right"):
            deco.append({"id": "mark_" + ("w" if side == "left" else "e"), "face": side,
                         "material": "endmark", "size": [7.6, 8.55],
                         "at": [0.0, r(h / 2 - 4.3 - 0.06)]})
    return box("body", [W, h, ZB - ZF], [0, h / 2, zc], "facade",
               open=["bottom", "top"] if top_open else ["bottom"],
               faces=dict({"front": "back", "left": "endwall", "right": "endwall"},
                          **({} if top_open else {"top": "roof"})),
               decals=deco or None)


def roof_nodes():
    t = 0.15
    x0, x1, z0, z1 = -W / 2 + t, W / 2 - t, ZF + t, ZB - t
    top = ROOF + PARAPET
    return [
        yquad("roof", "roof", x0, x1, z0, z1, ROOF),
        # the parapet's inside, seen from the roof
        zquad("parapet_in_s", "coping", x0, x1, ROOF, top, z0, facing=1),
        zquad("parapet_in_n", "coping", x0, x1, ROOF, top, z1, facing=-1),
        xquad("parapet_in_w", "coping", z0, z1, ROOF, top, x0, facing=1),
        xquad("parapet_in_e", "coping", z0, z1, ROOF, top, x1, facing=-1),
        # its top
        yquad("coping_s", "coping", -W / 2, W / 2, ZF, z0, top),
        yquad("coping_n", "coping", -W / 2, W / 2, z1, ZB, top),
        yquad("coping_w", "coping", -W / 2, x0, z0, z1, top),
        yquad("coping_e", "coping", x1, W / 2, z0, z1, top),
    ]


def balconies():
    nodes = []
    zr = ZF - BAL + 0.06
    for k in range(1, 7):
        y = k * STOREY
        nodes.append(yquad(f"bal_{k}_floor", "slab", -W / 2, W / 2, ZF - BAL, ZF + 0.02, y))
        nodes.append(yquad(f"bal_{k}_soffit", "slab", -W / 2, W / 2, ZF - BAL, ZF + 0.02,
                           y - 0.16, up=False))
        nodes.append(zquad(f"bal_{k}_rail", "rail", -W / 2 + 0.05, W / 2 - 0.05, y - 0.16,
                           y + RAIL, zr, uvs=rail_uvs(W - 0.1)))
        nodes.append(xquad(f"bal_{k}_rail_w", "rail", zr, ZF, y - 0.16, y + RAIL, -W / 2 + 0.05,
                           facing=-1, uvs=rail_uvs(ZF - zr)))
        nodes.append(xquad(f"bal_{k}_rail_e", "rail", zr, ZF, y - 0.16, y + RAIL, W / 2 - 0.05,
                           uvs=rail_uvs(ZF - zr)))
        nodes.append(xquad(f"bal_{k}_partition", "partition", zr + 0.1, ZF, y, y + 1.9, 0.0))
    return nodes


def balcony_life():
    """What lives on the balconies: laundry, futons, blinds, air conditioners, two dishes."""
    S = STOREY
    zr = ZF - BAL + 0.06
    n = []
    # futons hung over the rail, 4 cm outside it
    for i, (k, x, m) in enumerate([(2, -4.6, "futon_a"), (4, 5.0, "futon_b"),
                                   (5, -5.8, "futon_b"), (6, 3.4, "futon_a")]):
        y = k * S
        n.append(zquad(f"futon_{i}", m, x - 0.5, x + 0.5, y + 0.3, y + RAIL + 0.05, zr - 0.05))
    # laundry on poles under the balcony ceiling, in the middle of the balcony
    for i, (k, x) in enumerate([(1, 4.8), (3, -4.8), (5, 4.6)]):
        y = k * S
        n.append(zquad(f"laundry_{i}", "laundry", x - 1.2, x + 1.2, y + 1.15, y + 1.93,
                       ZF - 0.65))
    for i, (k, x) in enumerate([(2, 4.3), (4, -4.3)]):
        y = k * S
        n.append(zquad(f"sudare_{i}", "sudare", x - 0.7, x + 0.7, y + 0.35, y + 2.1, ZF - 0.1))
    for i, (k, x) in enumerate([(1, -6.9), (3, 6.9), (6, -6.9)]):
        y = k * S
        n.append(box(f"ac_{i}", [0.8, 0.55, 0.28], [x, y + 0.275, ZF - 0.32], "ac",
                     open=["bottom"], faces={"back": "fan"}))
    for i, (k, x, yaw) in enumerate([(3, -1.3, 20), (5, 1.3, -20)]):
        y = k * S
        n.append({"id": f"dish_{i}", "op": "lathe", "profile": [[0.0, 0.0],
                  [0.28, 0.1]], "segments": 6, "caps": False, "material": "dish",
                  "transform": {"rotate": [-60, yaw, 0], "translate": [x, y + 1.25, zr - 0.25]}})
    return n


def ground():
    n = [box("hedge", [W - 0.4, 0.8, 0.5], [0, 0.4, ZF - BAL + 0.05], "hedge", open=["bottom"])]
    # bicycle shelter at the back, west end
    x0, x1, z0, z1 = -7.6, -2.8, ZB + 0.05, ZB + 2.3
    n.append(quad("shelter_roof", "shelter", [[x0, 2.25, z1], [x1, 2.25, z1],
                                              [x1, 2.45, z0], [x0, 2.45, z0]]))
    for i, x in enumerate((x0 + 0.1, x1 - 0.1)):
        n.append(box(f"shelter_post_{i}", [0.08, 2.24, 0.08], [x, 1.12, z1 - 0.15], "steel",
                     open=["top", "bottom"]))
    for i, (x, m) in enumerate([(-6.9, "bike_a"), (-5.6, "bike_b"), (-4.3, "bike_c"),
                                (-3.4, "bike_a")]):
        n.append(xquad(f"bike_{i}", m, z0 + 0.25, z0 + 1.85, 0.02, 1.02, x))
    n.append(cyl("pipe", 0.06, ROOF + 0.2, [-1.0, (ROOF + 0.2) / 2, ZB + 0.1], "steel"))
    return n


def roof_things():
    top = ROOF
    n = [box("tank_stand", [2.0, 0.52, 2.0], [0, top + 0.25, 0], "steel", open=["bottom"]),
         box("tank", [2.4, 1.5, 2.4], [0, top + 2.0 - 0.75, 0], "tank", open=["bottom"])]
    for i, (x, z, yaw) in enumerate([(-5.5, -1.2, 30), (-3.0, -3.0, 15), (4.6, -2.2, -35)]):
        n.append(cyl(f"mast_{i}", 0.03, 2.4, [x, top + 1.2, z], "steel", segments=3))
        n.append({"id": f"yagi_{i}", "op": "mesh", "material": "antenna",
                  "vertices": [[-0.8, 1.9, 0], [0.8, 1.9, 0], [0.8, 1.42, 0], [-0.8, 1.42, 0]],
                  "faces": [[0, 1, 2, 3]],
                  "transform": {"rotate": [0, yaw, 0], "translate": [x, top, z]}})
    n.append(cyl("lightning_rod", 0.02, 2.6, [1.6, top + 1.3, 2.9], "steel", segments=3))
    return n


def stair_tower(flights=True):
    w, d = T_X1 - T_X0, T_Z1 - ZB
    h = T_TOP - T_BOT
    n = [box("stair_cage", [w, h, d], [(T_X0 + T_X1) / 2, (T_BOT + T_TOP) / 2, (ZB + T_Z1) / 2],
             "stair_wall", open=["bottom", "top", "back"])]
    # the cage's two outer corner columns, from the ground
    for i, x in enumerate((T_X0, T_X1)):
        n.append(box(f"cage_post_{i}", [0.22, T_TOP, 0.22], [x, T_TOP / 2, T_Z1],
                     "coping", open=["bottom", "top"]))
    if not flights:
        # the storey landings only, across both lanes
        for k in range(1, 8):
            n.append(yquad(f"landing_{k}", "stair", T_X0 + 0.02, T_X0 + LAND, ZB + 0.05,
                           T_Z1 - 0.05, k * STOREY))
        return n
    xa, xb = T_X0 + LAND, T_X1 - LAND
    zm = (ZB + T_Z1) / 2
    lanes = {"in": (ZB + 0.05, zm), "out": (zm, T_Z1 - 0.05)}
    for i in range(FLIGHTS):
        y0, y1 = i * RISE, (i + 1) * RISE
        z0, z1 = lanes["out" if i % 2 == 0 else "in"]
        if i % 2 == 0:   # outer lane, climbing east
            pts = [[xa, y0, z1], [xb, y1, z1], [xb, y1, z0], [xa, y0, z0]]
        else:            # inner lane, climbing west
            pts = [[xb, y0, z0], [xa, y1, z0], [xa, y1, z1], [xb, y0, z1]]
        n.append(quad(f"flight_{i}", "stair", pts))
        lx0, lx1 = (xb, T_X1 - 0.02) if i % 2 == 0 else (T_X0 + 0.02, xa)
        if i < FLIGHTS - 1:
            n.append(yquad(f"landing_{i}", "stair", lx0, lx1, ZB + 0.05, T_Z1 - 0.05, y1))
        else:   # the top landing meets the roof over the parapet
            n.append(yquad(f"landing_{i}", "stair", lx0, lx1, ZB + 0.05, T_Z1 - 0.05, y1))
    return n


LIT_OUT = 0.04       # a card's distance in front of its wall
# Where the facade texture draws them (8 texels a metre across, 16 a storey): balcony doors
# x 3.5 to 6.75 (either side), from the floor to 2.01; windows x 1.25 to 2.625, 0.84 to 1.85.
DOOR_X, WIN_X = (3.5, 6.75), (1.25, 2.625)
DOOR_Y, WIN_Y = (0.02, 12 * STOREY / 16), (5 * STOREY / 16, 11 * STOREY / 16)
# South face: (storey, side -1 west / +1 east, door or window, material). Clear of the blinds
# and the laundry; one behind a futon on the rail, one over the hedge on the ground floor.
LIT_SOUTH = [(0, -1, "win", "lit_win"), (1, -1, "door", "lit_door"), (2, 1, "win", "lit_win"),
             (3, 1, "door", "lit_door_b"), (4, -1, "win", "lit_win"), (4, 1, "door", "lit_door"),
             (5, -1, "door", "lit_door_b"), (6, 1, "win", "lit_win")]
# End walls (no windows drawn there, below the block number): (storey, -1 west / +1 east, z).
LIT_ENDS = [(1, -1, -2.6), (2, -1, 1.2), (0, 1, 1.2), (3, 1, -2.6)]


def lit_windows(ends=True):
    """The lit window cards, one mesh node a face (south, and the two ends)."""
    S = STOREY
    v, f, fm = [], [], []

    def add(pts, mat):
        f.append(list(range(len(v), len(v) + 4)))
        v.extend([[r(c) for c in p] for p in pts])
        fm.append(mat)

    z = ZF - LIT_OUT
    for k, side, kind, mat in LIT_SOUTH:
        (a, b), (y0, y1) = (DOOR_X, DOOR_Y) if kind == "door" else (WIN_X, WIN_Y)
        x0, x1 = (a, b) if side > 0 else (-b, -a)
        y0, y1 = k * S + y0, k * S + y1
        add([[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]], mat)    # seen from -Z
    nodes = [{"id": "lit_south", "op": "mesh", "vertices": v, "faces": f, "face_materials": fm}]
    if not ends:
        return nodes
    v, f, fm = [], [], []
    for k, side, zc in LIT_ENDS:
        x = side * (W / 2 + LIT_OUT)
        y0, y1 = k * S + WIN_Y[0], k * S + WIN_Y[1]
        z0, z1 = zc - 0.55, zc + 0.55
        if side > 0:    # seen from +X: +Z to the right
            add([[x, y1, z0], [x, y1, z1], [x, y0, z1], [x, y0, z0]], "lit_win")
        else:           # seen from -X: -Z to the right
            add([[x, y1, z1], [x, y1, z0], [x, y0, z0], [x, y0, z1]], "lit_win")
    nodes.append({"id": "lit_ends", "op": "mesh", "vertices": v, "faces": f, "face_materials": fm})
    return nodes


def level0():
    return (
        [body()] + roof_nodes() + balconies() + balcony_life() + ground() + roof_things()
        + stair_tower() + lit_windows()
    )


def level1():
    S = STOREY
    zr = ZF - BAL + 0.06
    n = [body(top_open=False)]
    for k in range(1, 7):
        n.append(zquad(f"bal_{k}_rail", "rail", -W / 2 + 0.05, W / 2 - 0.05, k * S - 0.16,
                       k * S + RAIL, zr, uvs=rail_uvs(W - 0.1)))
        n.append(yquad(f"bal_{k}_soffit", "slab", -W / 2, W / 2, ZF - BAL, ZF + 0.02,
                       k * S - 0.16, up=False))
    n += stair_tower(flights=False)
    n.append(box("tank", [2.4, 2.0, 2.4], [0, ROOF + 1.0, 0], "tank", open=["bottom"]))
    n.append(box("hedge", [W - 0.4, 0.8, 0.5], [0, 0.4, ZF - BAL + 0.05], "hedge",
                 open=["bottom"]))
    return n + lit_windows()


def level2():
    return [body(top_open=False, end_decals=False),
            box("stair_cage", [T_X1 - T_X0, ROOF + 1.1, T_Z1 - ZB],
                [(T_X0 + T_X1) / 2, (ROOF + 1.1) / 2, (ZB + T_Z1) / 2], "endwall",
                open=["bottom", "back"]),
            box("tank", [2.4, 2.0, 2.4], [0, ROOF + 1.0, 0], "tank", open=["bottom"])
            ] + lit_windows(ends=False)


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "danchi",
        "budget": {"triangles": 600},
        "sheets": {"danchi": {"image": "art/danchi_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               "solid", open=open)


def ramp(id, xa, xb, ya, yb, z0, z1, t=0.25):
    """A flight from (xa, ya) up to (xb, yb): its walkable top, its underside and its sides; the
    ends are open (they meet landings or the ground)."""
    if ya <= 0:   # the first flight: a wedge on the ground
        v = [[xa, ya, z0], [xb, yb, z0], [xb, yb, z1], [xa, ya, z1], [xb, 0, z0], [xb, 0, z1]]
        return {"id": id, "op": "mesh", "material": "solid",
                "vertices": [[r(c) for c in p] for p in v],
                "faces": [[3, 2, 1, 0], [0, 4, 5, 3], [0, 1, 4], [2, 3, 5]]}
    v = [[xa, ya, z0], [xb, yb, z0], [xb, yb, z1], [xa, ya, z1],
         [xa, max(ya - t, 0), z0], [xb, yb - t, z0], [xb, yb - t, z1], [xa, max(ya - t, 0), z1]]
    if xb > xa:
        faces = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6]]
    else:
        faces = [[0, 1, 2, 3], [7, 6, 5, 4], [4, 5, 1, 0], [6, 7, 3, 2]]
    return {"id": id, "op": "mesh", "material": "solid",
            "vertices": [[r(c) for c in p] for p in v], "faces": faces}


def collision():
    """Boxes and ramps. Parts that touch meet edge to edge or with a centimetre between them, so
    no two faces lie flush."""
    t = 0.2
    e = 0.01
    S = STOREY
    top = ROOF + PARAPET
    n = [solid("body", -W / 2, W / 2, 0, ROOF, ZF, ZB, open=["bottom"]),
         solid("parapet_s", -W / 2, W / 2, ROOF, top, ZF, ZF + t, open=["bottom"]),
         solid("parapet_n", -W / 2, W / 2, ROOF, top, ZB - t, ZB, open=["bottom"]),
         solid("parapet_w", -W / 2, -W / 2 + t, ROOF, top, ZF + t, ZB - t,
               open=["bottom", "back", "front"]),
         solid("parapet_e", W / 2 - t, W / 2, ROOF, top, ZF + t, ZB - t,
               open=["bottom", "back", "front"]),
         solid("tank", -1.2, 1.2, ROOF, ROOF + 2.0, -1.2, 1.2, open=["bottom"])]
    # balconies: a slab and a solid front rail. Only the first is a ledge to reach: a double jump
    # from the ground grabs its rail and climbs in (2.69). Each balcony's slab is right over the
    # one below, its rail top 1.44 m under the next slab (the body is 1.6 m), so from a balcony
    # there is no jump to the next; standing on a rail puts the head in the slab above (alpha
    # review, r08 #9: accepted, the stair on the back is the way to the roof)
    for k in range(1, 7):
        y = k * S
        n.append(solid(f"bal_{k}", -W / 2, W / 2, y - 0.2, y, ZF - BAL, ZF, open=["front"]))
        n.append(solid(f"bal_{k}_rail", -W / 2, W / 2, y, y + RAIL, ZF - BAL, ZF - BAL + t,
                       open=["bottom"]))
    n.append(solid("hedge", -W / 2 + 0.2, W / 2 - 0.2, 0, 0.8, ZF - BAL - 0.2, ZF - BAL + 0.3,
                   open=["bottom"]))
    # the stair: three cage walls from 2.52 up (open underneath, open on top), flights as ramps
    n += [solid("cage_w", T_X0 - t, T_X0, T_BOT, T_TOP, ZB, T_Z1, open=["back", "front"]),
          solid("cage_e", T_X1, T_X1 + t, T_BOT, T_TOP, ZB, T_Z1, open=["back", "front"]),
          solid("cage_n", T_X0 - t, T_X1 + t, T_BOT, T_TOP, T_Z1, T_Z1 + t)]
    xa, xb = T_X0 + LAND, T_X1 - LAND
    zm = (ZB + T_Z1) / 2
    for i in range(FLIGHTS):
        y0, y1 = i * RISE, (i + 1) * RISE
        if i % 2 == 0:   # outer lane, climbing east, to a landing at the east end
            n.append(ramp(f"flight_{i}", xa, xb, y0, y1, zm + e, T_Z1 - e))
            n.append(solid(f"landing_{i}", xb, T_X1 - e, y1 - 0.25, y1, ZB + e, T_Z1 - e))
        else:            # inner lane, climbing west, to a landing at the west end
            n.append(ramp(f"flight_{i}", xb, xa, y0, y1, ZB + e, zm - e))
            n.append(solid(f"landing_{i}", T_X0 + e, xa, y1 - 0.25, y1, ZB + e, T_Z1 - e))
    n.append(solid("shelter", -7.6, -2.8, 2.2, 2.45, ZB + e, ZB + 2.3))
    return {
        "format": "mei-asset", "version": 1, "name": "danchi_col",
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
    write("danchi.asset.json", recipe())
    write("danchi_col.asset.json", collision())
