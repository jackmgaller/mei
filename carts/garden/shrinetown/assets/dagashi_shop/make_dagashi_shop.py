#!/usr/bin/env python3
"""Writes dagashi_shop.asset.json, dagashi_shop_col.asset.json, dagashi_shop.cameras.json and
art/dagashi_sheet.png (+ .sheet.json) beside this file: shrine town's old sweet shop (駄菓子屋)
at the alley corner (spec 3.3, the grey box's 5 x 5 x 4.4 block), cut from the lab model
(examples/assets/lab/dagashi_shop, 668 triangles) to 400. Run once and commit the outputs (needs
Pillow): python3 carts/garden/shrinetown/assets/dagashi_shop/make_dagashi_shop.py

Asset frame: origin at the centre of the 4.9 x 5.0 m footprint at the alley's ground, the shop
front toward -Z. The lab's shop was a 1.75 m deep stall; here it is a house 3.4 m deep (the
shop in its front half, the family behind the shelves), so it fills its block and reads as a
house from the alley roofs. Eaves 3.2, ridge 4.45; the striped awning is a ledge at 2.45-2.65
from which the eave is 0.6 m up.

Kept from the lab: the red-and-cream awning, the 駄菓子 おもちゃ signboard, the 氷 noren, the
shelves of sweets and the kuji board, the jars on the counter and the beckoning cat, the ice
freezer, the drinks machine, the crate of ramune, the アイス flag, two red lanterns and the boy
in the gold cap. The cat, the ramune and the side and back walls are drawn on textures now.

Textures: art/dagashi_sheet.png is the lab's sheet (examples/assets/lab/dagashi_shop/art) with
new cells below it, drawn here: the side and back elevations (on the town's shared plaster from
../town_alley_house_a/art/town_common.png), a sweet jar, the cat and the ramune bottles. Roof
tile and plaster are the town's shared tiles."""
import json, math, os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(ROOT, "examples", "assets", "lab", "dagashi_shop", "art")
COMMON = os.path.join(HERE, "..", "town_alley_house_a", "art", "town_common.png")


def r(v):
    return [r(x) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def orient(verts, faces, outward):
    out = []
    for k, f in enumerate(faces):
        pts = [verts[i] for i in f]
        n = newell(pts)
        if isinstance(outward, tuple):
            ctr = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
            ref = sub(ctr, outward[1])
        else:
            ref = outward
        out.append(list(f) if dot(n, ref) >= 0 else list(reversed(f)))
    return out


def mesh(id_, mat, verts, faces, outward):
    return {"id": id_, "op": "mesh", "material": mat, "vertices": [r(v) for v in verts],
            "faces": orient(verts, faces, outward)}


def quad_z(id_, mat, x0, x1, y0, y1, z, facing=-1):
    return mesh(id_, mat, [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]], [[0, 1, 2, 3]], [0, 0, facing])


def box(id_, mat, size, at, open_=None, faces=None, decals=None, rot=None, mods=None):
    n = {"id": id_, "op": "box", "size": r(list(size)), "material": mat, "transform": {"translate": r(list(at))}}
    if rot:
        n["transform"]["rotate"] = r(list(rot))
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    if mods:
        n["modifiers"] = mods
    return n


def bx(id_, mat, x0, x1, y0, y1, z0, z1, open_=None, **kw):
    return box(id_, mat, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2], open_, **kw)


def cyl(id_, mat, radius, height, seg, at, caps=True, rot=None):
    n = {"id": id_, "op": "cylinder", "radius": radius, "height": height, "segments": seg, "material": mat,
         "transform": {"translate": r(list(at))}}
    if not caps:
        n["caps"] = False
    if rot:
        n["transform"]["rotate"] = list(rot)
    return n


def solid(id_, verts, faces):
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    return mesh(id_, "solid", verts, faces, ("away", c))


def cuboid(id_, x0, x1, y0, y1, z0, z1):
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
         [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


# ------------------------------------------------------------------------------- dimensions
HX = 2.0                     # side walls' outer faces
WT = 0.12                    # wall thickness
ZF, ZB = -0.95, 2.45         # the house's front (the shop opening) and back
ZC = (ZF + ZB) / 2           # the ridge line
SPAN = 2.05                  # eave half-span from the ridge (0.35 m overhang)
EAVE, RIDGE = 3.2, 4.45      # the roof's outer surface at the eaves and the ridge
ROOF_T = 0.12
SHOP_Z = 0.75                # the shelves' wall: the shop in front, the house behind
FLOOR = 0.2
CEIL = 2.45
PAVE_Z = -2.5


def roof_out(d):
    return RIDGE - d * (RIDGE - EAVE) / SPAN


def roof_in(d):
    return roof_out(d) - ROOF_T


# ------------------------------------------------------------------------------- textures
def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (a,)


CLEAR = (0, 0, 0, 0)
BOARD, BOARD_D, BOARD_L = rgb("#6e4c30"), rgb("#3e2a1c"), rgb("#7d5a3a")
FRAME, PAPER, PAPER_D = rgb("#4a3122"), rgb("#efe8cf"), rgb("#d8cfb0")


def plaster_fill(w, h):
    tile = Image.open(COMMON).convert("RGBA").crop((128, 0, 160, 32))
    im = Image.new("RGBA", (w, h))
    for y in range(0, h, 32):
        for x in range(0, w, 32):
            im.paste(tile, (x, y))
    return im


def boards(d, x0, y0, x1, y1):
    d.rectangle([x0, y0, x1, y1], fill=BOARD)
    for x in range(x0, x1 + 1, 4):
        d.line([(x, y0), (x, y1)], fill=BOARD_D)
        d.line([(x + 2, y0 + 1), (x + 2, y0 + 3)], fill=BOARD_L)
    d.line([(x0, y0), (x1, y0)], fill=FRAME)


def shoji(d, x0, y0, x1, y1, n=3):
    d.rectangle([x0, y0, x1, y1], fill=FRAME)
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], fill=PAPER)
    for k in range(1, n):
        x = x0 + (x1 - x0) * k // n
        d.line([(x, y0), (x, y1)], fill=FRAME)
        y = y0 + (y1 - y0) * k // n
        d.line([(x0, y), (x1, y)], fill=FRAME)
    d.line([(x0 + 1, y1 - 1), (x1 - 1, y1 - 1)], fill=PAPER_D)


def draw_side():
    """The side wall's outline face (3.4 m wide, 0 to the gable's top), as fit maps it: plaster,
    a board skirt to 0.9 m, a shoji window in the middle. The pentagon cuts the top corners."""
    w, h = 56, 72
    top = roof_in(0) + 0.02
    im = plaster_fill(w, h)
    d = ImageDraw.Draw(im)
    py = lambda y: int(round((top - y) / top * h))
    boards(d, 0, py(0.9), w - 1, h - 1)
    shoji(d, w // 2 - 7, py(2.15), w // 2 + 6, py(1.3))
    return im


def draw_back():
    w, h = 64, 56
    im = plaster_fill(w, h)
    d = ImageDraw.Draw(im)
    py = lambda y: int(round((roof_in(ZB - ZC) + 0.02 - y) / (roof_in(ZB - ZC) + 0.02) * h))
    boards(d, 0, py(0.9), w - 1, h - 1)
    shoji(d, 12, py(2.1), 25, py(1.35))
    # the back door: a dark sliding door
    d.rectangle([40, py(1.85), 52, h - 1], fill=FRAME)
    d.rectangle([41, py(1.85) + 1, 51, h - 2], fill=rgb("#5e4230"))
    d.line([(46, py(1.85) + 1), (46, h - 2)], fill=FRAME)
    return im


def draw_jar():
    im = Image.new("RGBA", (16, 16), CLEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 3], fill=rgb("#d63a2a"))
    d.rectangle([0, 3, 15, 3], fill=rgb("#8a2418"))
    d.rectangle([0, 4, 15, 15], fill=rgb("#cfe6ea"))
    cols = ["#f08a2a", "#ee7aa8", "#66bc62", "#f2cc3a", "#e04a30", "#5a9ae0"]
    for k in range(18):
        x, y = (k * 7) % 14 + 1, 6 + (k * 5) % 9
        d.rectangle([x, y, x + 1, y], fill=rgb(cols[k % len(cols)]))
    d.line([(1, 5), (1, 14)], fill=rgb("#f4fbfc"))
    return im


def draw_cat():
    """The beckoning cat, front on, its raised paw on the right; cut out round its outline."""
    im = Image.new("RGBA", (16, 24), CLEAR)
    d = ImageDraw.Draw(im)
    W_, R_, G_, K_ = rgb("#f4f0e6"), rgb("#d63a2a"), rgb("#e0b84a"), rgb("#2a2420")
    d.polygon([(3, 2), (5, 5), (2, 6)], fill=W_)            # ears
    d.polygon([(11, 2), (11, 6), (9, 5)], fill=W_)
    d.ellipse([2, 4, 12, 13], fill=W_)                       # head
    d.rectangle([3, 12, 11, 22], fill=W_)                    # body
    d.rectangle([2, 22, 12, 23], fill=W_)
    d.rectangle([12, 5, 14, 12], fill=W_)                    # the raised paw
    d.point((13, 5), fill=rgb("#f0b0b0"))
    d.point((5, 8), fill=K_); d.point((9, 8), fill=K_)       # eyes, nose
    d.point((7, 10), fill=R_)
    d.rectangle([3, 13, 11, 14], fill=R_)                    # collar and bell
    d.rectangle([6, 15, 8, 16], fill=G_)
    d.rectangle([5, 18, 9, 21], fill=G_)                     # the koban coin
    d.point((4, 3), fill=rgb("#f0b0b0")); d.point((10, 3), fill=rgb("#f0b0b0"))
    return im


def draw_bottles():
    """Four ramune bottles standing in a crate, seen from the side; cut out above the crate."""
    im = Image.new("RGBA", (24, 12), CLEAR)
    d = ImageDraw.Draw(im)
    for k in range(4):
        x = 1 + k * 6
        d.rectangle([x, 4, x + 3, 11], fill=rgb("#8fd3e8"))
        d.rectangle([x + 1, 1, x + 2, 4], fill=rgb("#8fd3e8"))
        d.rectangle([x + 1, 0, x + 2, 0], fill=rgb("#3c70c8"))
        d.line([(x, 6), (x, 10)], fill=rgb("#d8f2f8"))
        d.rectangle([x + 1, 6, x + 2, 7], fill=rgb("#3c70c8"))
    return im


def write_sheet():
    lab = Image.open(os.path.join(LAB, "shop_sheet.png")).convert("RGBA")
    cells = json.load(open(os.path.join(LAB, "shop_sheet.sheet.json")))["cells"]
    sheet = Image.new("RGBA", (256, 264), CLEAR)
    sheet.paste(lab, (0, 0))
    x = 0
    for name, im in (("side", draw_side()), ("back", draw_back()), ("jar", draw_jar()), ("cat", draw_cat()),
                     ("bottles", draw_bottles())):
        sheet.paste(im, (x, 192))
        cells[name] = [x, 192, im.width, im.height]
        x += im.width
    sheet.save(os.path.join(ART, "dagashi_sheet.png"))
    with open(os.path.join(ART, "dagashi_sheet.sheet.json"), "w") as fh:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, fh, indent=1)


# ------------------------------------------------------------------------------- materials
def cell(name, bits=4, **kw):
    t = {"sheet": "shop", "cell": name, "bits": bits, "projection": "fit"}
    t.update(kw)
    return t


M = {
    "paving": {"color": "#a9a69c", "tag": "floor", "texture": {
        "pattern": "tile", "colors": ["#a7a49a", "#7f7c74", "#b6b3a8"], "params": {"count": 2, "grout": 1},
        "projection": "planar", "axis": "y", "scale": [1, 1]}},
    "wood": {"color": "#8b6a47", "texture": {
        "pattern": "planks", "colors": ["#8b6a47", "#4e3822", "#7d5d3d", "#9a7852"], "params": {"boards": 4},
        "projection": "box", "scale": [1, 1]}},
    "plaster": {"color": "#e0d6bc", "tag": "wall", "texture": {
        "sheet": "town_common", "cell": "plaster", "projection": "box", "scale": [2, 2]}},
    "kawara": {"color": "#565c64", "tag": "roof", "texture": {
        "sheet": "town_common", "cell": "kawara", "projection": "box", "scale": [2, 2]}},
    "awning": {"color": "#c9402f", "double_sided": True, "texture": {
        "pattern": "stripes", "colors": ["#cf4631", "#f1e8d0"], "params": {"count": 8},
        "projection": "box", "scale": [2, 2]}},
    "side": {"color": "#e0d6bc", "tag": "wall", "texture": cell("side")},
    "back": {"color": "#e0d6bc", "tag": "wall", "texture": cell("back")},
    "kanban": {"color": "#7a1c1a", "texture": cell("kanban", 8)},
    "shelf_a": {"color": "#4a3020", "texture": cell("shelf_a", 8)},
    "shelf_b": {"color": "#4a3020", "texture": cell("shelf_b", 8)},
    "kuji": {"color": "#e6d6a8", "texture": cell("kuji", 8)},
    "vending_front": {"color": "#bd2824", "texture": cell("vending", 8)},
    "freezer_sign": {"color": "#3c80d2", "texture": cell("freezer", 8)},
    "noren": {"color": "#243468", "double_sided": True, "texture": cell("noren")},
    "flag": {"color": "#2a6ec4", "double_sided": True, "texture": cell("flag", 8)},
    "jar": {"color": "#cfe6ea", "texture": cell("jar")},
    "cat": {"color": "#f4f0e6", "double_sided": True, "texture": cell("cat")},
    "bottles": {"color": "#8fd3e8", "double_sided": True, "texture": cell("bottles")},
    "lantern": {"color": "#e04a30", "class": "emissive"},
}
# palette-backed colours (7 surface)
for name, col in {"dark_wood": "#4a3122", "ridge": "#2b3239", "red": "#bd2824", "white": "#dfeaf0",
                  "pole": "#59636b", "skin": "#f0c8a0", "gold": "#e0b84a"}.items():
    M[name] = {"color": col, "palette": True}


# ------------------------------------------------------------------------------- parts
def side_walls():
    """Each side wall a pentagon (the gable end) extruded WT thick; the right one mirrored."""
    d_front, d_back = ZC - ZF, ZB - ZC
    pts = [[ZF, 0], [ZB, 0], [ZB, roof_in(d_back) + 0.02], [ZC, roof_in(0) + 0.02],
           [ZF, roof_in(d_front) + 0.02]]
    # outline x is -z after the turn below ([0, 90, 0] turns +X to -Z)
    pts = [[-z, y] for z, y in pts]
    return {"id": "side_walls", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}], "children": [
        {"id": "side_wall", "op": "extrude", "material": "plaster", "depth": WT, "points": r(pts),
         "faces": {"front": "side"},
         "transform": {"rotate": [0, 90, 0], "translate": [HX - WT / 2, 0, 0]}}]}


def roof(ridge=True):
    """The two slopes as one chevron, kawara on top and under, dark at its gable edges."""
    zs = [ZC - SPAN, ZC, ZC + SPAN]
    out = [[zs[0], roof_out(SPAN)], [zs[1], roof_out(0)], [zs[2], roof_out(SPAN)],
           [zs[2], roof_in(SPAN)], [zs[1], roof_in(0)], [zs[0], roof_in(SPAN)]]
    pts = [[-z, y] for z, y in out]
    nodes = [{"id": "roof", "op": "extrude", "material": "kawara", "depth": 2 * HX + 0.5, "points": r(pts),
              "faces": {"front": "ridge", "back": "ridge"},
              "transform": {"rotate": [0, 90, 0], "translate": [0, 0, 0]}}]
    if ridge:
        nodes.append(box("ridge", "ridge", [2 * HX + 0.6, 0.12, 0.2], [0, RIDGE + 0.03, ZC], ["bottom"]))
    return nodes


def walls(detail=True):
    hi = roof_in(ZC - ZF - 0.04) + 0.02
    nodes = [
        # the wall over the shop's opening, with the signboard
        bx("front_wall", "plaster", -HX + WT - 0.01, HX - WT + 0.01, CEIL, hi, ZF + 0.04, ZF + 0.04 + WT, ["bottom"],
           decals=[{"id": "kanban", "face": "back", "material": "kanban", "size": [2.9, 0.55],
                    "at": [0, 0.04]}] if detail else None,
           faces=None if detail else {"back": "kanban"}),
        bx("back_wall", "plaster", -HX + WT - 0.01, HX - WT + 0.01, 0, roof_in(ZB - ZC - 0.04) + 0.02,
           ZB - WT - 0.04, ZB - 0.04, ["bottom"], faces={"front": "back"}),
    ]
    shelf_decals = [{"id": "shelf_l", "face": "back", "material": "shelf_a", "size": [1.4, 1.84], "at": [-1.0, -0.12]},
                    {"id": "shelf_r", "face": "back", "material": "shelf_b", "size": [1.4, 1.84], "at": [1.0, -0.12]},
                    {"id": "kuji", "face": "back", "material": "kuji", "size": [0.5, 0.42], "at": [0, 0.35]}]
    nodes.append(bx("shelves", "dark_wood", -HX + WT - 0.015, HX - WT + 0.015, FLOOR, CEIL + 0.01,
                    SHOP_Z, SHOP_Z + 0.1, ["bottom", "top"], decals=shelf_decals if detail else None,
                    faces=None if detail else {"back": "shelf_a"}))
    return nodes


def shop_floor():
    return [bx("slab", "wood", -HX + WT - 0.03, HX - WT + 0.03, 0, FLOOR, ZF - 0.05, SHOP_Z + 0.02, ["bottom"]),
            mesh("ceiling", "dark_wood", [[-HX + WT, CEIL, ZF + WT], [HX - WT, CEIL, ZF + WT],
                                          [HX - WT, CEIL, SHOP_Z], [-HX + WT, CEIL, SHOP_Z]],
                 [[0, 1, 2, 3]], [0, -1, 0]),
            {"id": "pillars", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}], "children": [
                bx("pillar", "wood", HX - WT - 0.27, HX - WT + 0.07, 0, CEIL + 0.01, ZF - 0.1, ZF + 0.2,
                   ["bottom", "top"])]}]


def pavement():
    return [bx("pavement", "paving", -2.45, 2.45, 0, 0.07, PAVE_Z, ZF + 0.1, ["bottom"])]


def awning(detail=True):
    nodes = [box("awning", "awning", [3.7, 0.05, 1.38], [0, 2.57, -1.555], rot=[-12, 0, 0]),
             bx("valance", "awning", -1.81, 1.81, 2.2, 2.42, -2.25, -2.21, ["top"])]
    if detail:
        nodes.append({"id": "awning_poles", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}],
                      "children": [cyl("awning_pole", "pole", 0.03, 2.38, 4, [1.85, 1.19, -2.1], caps=False)]})
        for k, (x0, x1) in enumerate(((-1.45, -0.51), (-0.47, 0.47), (0.51, 1.45))):
            nodes.append(quad_z("noren_%d" % k, "noren", x0, x1, 1.9, CEIL - 0.03, ZF - 0.06))
    return nodes


def front_things():
    nodes = [
        bx("vending", "red", 0.82, 1.68, 0.07, 1.82, -1.81, -1.09, ["bottom"], faces={"back": "vending_front"}),
        bx("freezer", "white", -1.5, -0.5, 0.06, 0.87, -1.75, -1.15, ["bottom"],
           decals=[{"id": "ice", "face": "back", "material": "freezer_sign", "size": [0.8, 0.22], "at": [0, 0.08]}]),
        bx("freezer_lid", "pole", -1.54, -0.46, 0.86, 0.92, -1.79, -1.11, ["bottom"]),
        bx("crate", "wood", -0.12, 0.43, 0.06, 0.35, -1.75, -1.35, ["bottom"]),
        mesh("bottles", "bottles", [[-0.08, 0.6, -1.55], [0.39, 0.6, -1.55], [0.39, 0.33, -1.55], [-0.08, 0.33, -1.55]],
             [[0, 1, 2, 3]], [0, 0, -1]),
        {"id": "lanterns", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}],
         "children": [cyl("lantern", "lantern", 0.15, 0.3, 4, [0.5, 2.15, -1.62], rot=[0, 45, 0])]},
        cyl("flag_pole", "pole", 0.025, 2.9, 4, [-2.3, 1.5, -1.2], caps=False),
        cyl("flag_arm", "pole", 0.02, 0.5, 3, [-2.07, 2.88, -1.2], caps=False, rot=[0, 0, 90]),
        quad_z("flag", "flag", -2.28, -1.9, 1.45, 2.85, -1.2),
    ]
    return nodes


def counter():
    nodes = [bx("counter", "wood", -1.2, 1.2, FLOOR - 0.01, 1.15, -0.55, -0.05, ["bottom"])]
    for k, x in enumerate((-0.95, -0.6, 0.75)):
        nodes.append(bx("jar_%d" % k, "jar", x - 0.11, x + 0.11, 1.14, 1.42, -0.42, -0.2, ["bottom"]))
    nodes.append(quad_z("cat", "cat", 0.12, 0.42, 1.14, 1.6, -0.36))
    return nodes


def kid():
    """The boy in the gold cap at the freezer, his back to the alley."""
    x, z = -0.2, -1.05
    return [bx("kid_legs", "skin", x - 0.1, x + 0.1, 0.06, 0.46, z - 0.025, z + 0.025, ["bottom"]),
            bx("kid_body", "white", x - 0.15, x + 0.15, 0.45, 0.76, z - 0.06, z + 0.06, ["bottom"]),
            bx("kid_head", "skin", x - 0.085, x + 0.085, 0.75, 0.92, z - 0.095, z + 0.095, ["bottom"]),
            bx("kid_cap", "gold", x - 0.12, x + 0.12, 0.88, 0.96, z - 0.16, z + 0.13, ["bottom"])]


# ------------------------------------------------------------------------------- levels
L0 = (pavement() + [side_walls()] + walls() + shop_floor() + roof() + awning() + front_things()
      + counter() + kid())

L1 = ([side_walls()] + walls(False) + roof(False)
      + [box("awning", "awning", [3.7, 0.05, 1.38], [0, 2.57, -1.555], rot=[-12, 0, 0]),
         bx("vending", "red", 0.82, 1.68, 0.07, 1.82, -1.81, -1.09, ["bottom"], faces={"back": "vending_front"}),
         bx("freezer", "white", -1.5, -0.5, 0.0, 0.9, -1.75, -1.15, ["bottom"]),
         bx("floor", "wood", -HX + WT - 0.01, HX - WT + 0.01, 0, FLOOR, ZF - 0.02, SHOP_Z + 0.02, ["bottom"]),
         mesh("ceiling", "dark_wood", [[-HX + WT, CEIL, ZF + WT], [HX - WT, CEIL, ZF + WT],
                                       [HX - WT, CEIL, SHOP_Z], [-HX + WT, CEIL, SHOP_Z]], [[0, 1, 2, 3]], [0, -1, 0])])

L2 = [bx("house", "plaster", -HX, HX, 0, EAVE, ZF, ZB, ["bottom"], faces={"back": "shelf_a"}),
      {"id": "roof", "op": "extrude", "material": "kawara", "depth": 2 * HX + 0.4,
       "points": r([[-(ZC - SPAN), EAVE - 0.06], [-(ZC + SPAN), EAVE - 0.06], [-ZC, RIDGE]]),
       "faces": {"front": "plaster", "back": "plaster"}, "transform": {"rotate": [0, 90, 0]}},
      box("awning", "awning", [3.7, 0.05, 1.38], [0, 2.57, -1.555], rot=[-12, 0, 0])]

recipe = {
    "format": "mei-asset", "version": 1, "name": "dagashi_shop",
    "budget": {"triangles": 400},
    "sheets": {"shop": {"image": "art/dagashi_sheet.png"},
               "town_common": {"image": "../town_alley_house_a/art/town_common.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": L0,
    "lod": {"levels": [{"distance": 24, "nodes": L1}, {"distance": 60, "nodes": L2}], "band": 2},
}

# ------------------------------------------------------------------------------- collision
CR, CE = 4.32, 3.2          # collision ridge and eave: 27.6 degrees, walkable
C = [cuboid("house", -HX, HX, 0, EAVE - 0.01, ZF, ZB),
     solid("roof", [[-HX - 0.25, CE, ZC - SPAN], [HX + 0.25, CE, ZC - SPAN], [HX + 0.25, CE, ZC + SPAN],
                    [-HX - 0.25, CE, ZC + SPAN], [-HX - 0.25, CR, ZC], [HX + 0.25, CR, ZC]],
           [[0, 1, 2, 3], [0, 1, 5, 4], [3, 2, 5, 4], [0, 4, 3], [1, 5, 2]]),
     # the awning: a ledge 0.2 thick, 0.55-0.75 under the eave
     cuboid("awning", -1.9, 1.9, 2.45, 2.65, -2.15, ZF - 0.01),
     cuboid("vending", 0.82, 1.68, 0, 1.82, -1.81, -1.09),
     cuboid("freezer", -1.52, -0.48, 0, 0.92, -1.77, -1.13)]
col = {"format": "mei-asset", "version": 1, "name": "dagashi_shop_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": C}

cams = [
    {"name": "alley", "eye": [-1.0, 1.6, -6.5], "target": [0, 1.5, 0]},
    {"name": "corner", "eye": [-6.0, 1.6, -5.0], "target": [0, 1.8, 0.5]},
    {"name": "counter", "eye": [0.4, 1.3, -2.2], "target": [0, 1.2, 0.5]},
    {"name": "alley_roof", "eye": [8.0, 7.6, -4.0], "target": [0, 3.2, 0.5]},
    {"name": "on_awning", "eye": [1.0, 4.3, -3.6], "target": [0, 3.6, 0.8]},
    {"name": "behind", "eye": [4.5, 1.6, 7.0], "target": [0, 1.8, 0.5]},
]

if __name__ == "__main__":
    os.makedirs(ART, exist_ok=True)
    write_sheet()
    for name, data in (("dagashi_shop.asset.json", recipe), ("dagashi_shop_col.asset.json", col),
                       ("dagashi_shop.cameras.json", cams)):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(data, fh, indent=1)
            fh.write("\n")
    print("wrote dagashi_shop, dagashi_shop_col, dagashi_shop.cameras.json, art/dagashi_sheet.png")
