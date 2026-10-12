#!/usr/bin/env python3
"""Writes the shrine town's station newsstand: art/newsstand_sheet.png (+ .sheet.json),
art/cat_face.png, newsstand.asset.json and newsstand_col.asset.json.

Adapted from the lab model (examples/assets/lab/newsstand, 628 triangles), whose sheet it reads
(the goods shelves, the magazines, the pegged magazines, the valance, the door, the plates, the
lucky cat's face). Same size (3.1 x 1.9 m plinth, roof 2.55) and the same things: the blue
enamel kiosk with its キオスク fascia, the counter with newspapers, a sweets box and the lucky cat,
magazine racks, the 号外 board, a red standing ashtray, a stool, and the staff door at the back.
The cut: the side walls are thin boxes whose outer faces carry the posters, the clock and the
station mark painted in; the shelves of goods (with the drinks fridge) and the back door are
decals; the hanging magazines and the valance are cutout cards. The sign and the board are
redrawn so their lettering is not clipped.

The roof (2.55 m, flat, tin on top) is a step from the plaza: the collision's roof is a slab
0.3 m beyond the walls on the sides and 0.4 m over the counter, a ledge to grab.

Run: python3 carts/garden/shrinetown/assets/newsstand/gen_newsstand.py
(needs Pillow and macOS's Hiragino Sans for the lettering)
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "newsstand")
LAB = os.path.join(LABDIR, "art", "newsstand_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"

BLUE = (42, 108, 180)
DBLUE = (27, 72, 128)
TILE = (47, 114, 188)
GROUT = (31, 85, 144)
WHITE = (242, 239, 230)
CREAM = (232, 226, 208)
YELLOW = (240, 196, 60)
RED = (216, 64, 47)
INK = (40, 38, 44)

# ---- dimensions (metres) ---------------------------------------------------------------
WX = 1.34                    # side walls' centres (0.08 thick: 1.30-1.38)
IN = 1.30                    # inside face of the side walls
ZF, ZB = -0.75, 0.75         # front and back of the walls
ZS = 0.2                     # the shelf wall's front, behind the counter
Y0, Y1 = 0.1, 2.45           # walls: on the plinth, under the roof
COUNTER = 1.02
FASCIA = 1.97                # fascia bottom
ROOF = (2.45, 2.55)
ROOF_Z = (-1.15, 0.95)
ROOF_X = 1.65


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def text(d, xy, s, size, fill):
    d.fontmode = "1"
    d.text(xy, s, font=ImageFont.truetype(FONT, size), fill=fill)


def rect(d, x0, y0, x1, y1, fill):
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill)


def draw_sign():
    """84 x 24: the fascia (half width, TEXTURES.md's cut). Blue board, white rules, キオスク."""
    im = Image.new("RGBA", (84, 24), BLUE + (255,))
    d = ImageDraw.Draw(im)
    rect(d, 0, 0, 84, 2, WHITE)
    rect(d, 0, 22, 84, 24, WHITE)
    text(d, (10, 3), "キオスク", 16, WHITE)
    return im


def draw_board():
    """32 x 48: the extra-edition sandwich board, 号外."""
    im = Image.new("RGBA", (32, 48), (236, 226, 190, 255))
    d = ImageDraw.Draw(im)
    for box in ((0, 0, 32, 3), (0, 45, 32, 48), (0, 0, 2, 48), (30, 0, 32, 48)):
        rect(d, *box, DBLUE)
    rect(d, 3, 4, 29, 25, RED)
    text(d, (4, 7), "号外", 12, WHITE)
    for j, w in enumerate((22, 18, 23, 15, 20)):
        rect(d, 5, 29 + j * 3, 5 + w, 30 + j * 3, (50, 44, 40))
    return im


def tiles(w, h, t=8):
    """The enamel wall: t-texel tiles with a texel of darker grout."""
    im = Image.new("RGBA", (w, h), GROUT + (255,))
    d = ImageDraw.Draw(im)
    for y in range(0, h, t):
        for x in range(0, w, t):
            rect(d, x, y, x + t - 1, y + t - 1, TILE)
    return im


def clock(d, cx, cy):
    """An 11-texel station clock at ten to eight."""
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=INK)
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(244, 240, 228))
    d.line([cx, cy, cx, cy - 3], fill=INK)
    d.line([cx, cy, cx - 2, cy + 1], fill=INK)
    d.point((cx + 1, cy), fill=RED)


def emblem(d, cx, cy):
    """An 11-texel station mark: a red ring, white inside, a red bar."""
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=RED)
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=WHITE)
    d.line([cx - 2, cy, cx + 2, cy], fill=RED)
    d.line([cx, cy - 2, cx, cy + 2], fill=RED)


def poster(src, name):
    """The lab's 24 x 32 festival poster at 15 x 20."""
    return lab(src, name).resize((15, 20), Image.NEAREST)


def draw_side(src, which):
    """24 x 72 over a side wall's outer face, 1.5 x 2.35 m: drawn at 48 x 72 (3.1 x 3.3 cm a
    texel) and halved in width (TEXTURES.md's cut).
    Seen from outside, the right wall's front is the texture's left, the left wall's its right.
    A cream trim down the front edge, a poster toward the back, a clock or the station mark
    toward the front, high up."""
    im = tiles(48, 72)
    d = ImageDraw.Draw(im)
    front_left = which == "r"
    fx = 0 if front_left else 45
    rect(d, fx, 0, fx + 3, 72, CREAM)                  # the corner trim
    px = 27 if front_left else 6                       # the poster, toward the back
    im.paste(poster(src, "poster_a" if which == "l" else "poster_b"), (px, 30))
    cx = 13 if front_left else 34                      # the clock or mark, toward the front
    (emblem if which == "l" else clock)(d, cx, 17)
    return im.resize((24, 72), Image.BOX)


def draw_goods(src):
    """64 x 56: the lab's shelves with its drinks fridge standing at the left, drawn at 128 x 56
    and halved in width (TEXTURES.md's cut)."""
    im = lab(src, "goods").copy()
    im.paste(lab(src, "fridge").resize((26, 56), Image.NEAREST), (6, 0))
    return im.resize((64, 56), Image.BOX)


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (256, 160), (0, 0, 0, 0))
    cells = {}

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("sign", draw_sign(), 0, 0)
    put("goods", draw_goods(src), 0, 24)
    put("mags", lab(src, "mags"), 128, 24)
    put("hang", lab(src, "hang"), 0, 80)
    put("valance", lab(src, "valance"), 0, 100)
    put("board", draw_board(), 192, 24)
    put("door", lab(src, "door"), 224, 24)
    put("tobacco", lab(src, "tobacco"), 128, 80)
    put("card", lab(src, "card"), 168, 80)
    put("side_l", draw_side(src, "l"), 208, 80)
    put("side_r", draw_side(src, "r"), 232, 80)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "newsstand_sheet.png"))
    with open(os.path.join(HERE, "art", "newsstand_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")
    Image.open(os.path.join(LABDIR, "art", "cat_face.png")).save(os.path.join(HERE, "art", "cat_face.png"))


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
    t = {}
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n["transform"] = t
    return n


def span(id, x0, x1, y0, y1, z0, z1, material, **kw):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               material, **kw)


def quad(id, material, corners):
    return {"id": id, "op": "mesh", "material": material,
            "vertices": [[r(c) for c in p] for p in corners], "faces": [[0, 1, 2, 3]]}


def card_z(id, material, x0, x1, y0, y1, z_bottom, z_top=None):
    """A card facing -Z (corners counter-clockwise from the front), leaning back when z_top >
    z_bottom."""
    zt = z_bottom if z_top is None else z_top
    return quad(id, material, [[x0, y1, zt], [x1, y1, zt], [x1, y0, z_bottom], [x0, y0, z_bottom]])


def cyl(id, radius, height, at, material, segments, caps=True, rotate=None):
    t = {}
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n = {"id": id, "op": "cylinder", "radius": radius, "height": r(height), "segments": segments,
         "material": material, "transform": t}
    if not caps:
        n["caps"] = False
    return n


def fit(cell, bits=4):
    t = {"sheet": "art", "cell": cell, "projection": "fit"}
    if bits == 8:
        t["bits"] = 8
    return t


MATERIALS = {
    "enamel": {"color": "#2a6cb4", "tag": "wall",
               "texture": {"pattern": "tile", "size": 16, "colors": ["#2f72bc", "#1f5590"],
                           "params": {"count": 2, "grout": 1}, "projection": "box",
                           "scale": [0.8, 0.8]}},
    "concrete": {"color": "#b4b0a6", "tag": "floor",
                 "texture": {"sheet": "concrete", "cell": "wall", "projection": "box",
                             "scale": [4.0, 2.0]}},
    "tin": {"color": "#8a9098", "tag": "roof",
            "texture": {"sheet": "town_common", "cell": "tin", "projection": "box",
                        "scale": [2, 2]}},
    "roof_edge": {"color": "#7a8088", "palette": True},
    "laminate": {"color": "#b8895a", "tag": "counter",
                 "texture": {"pattern": "grain", "size": 16,
                             "colors": ["#c49a68", "#a87a4c", "#b78856"],
                             "params": {"rings": 3, "waves": 1}, "projection": "box",
                             "scale": [0.8, 0.8]}},
    "news": {"color": "#dcd8cc",
             "texture": {"pattern": "stripes", "size": 16, "colors": ["#e6e2d6", "#b9b5aa", "#d4d0c4"],
                         "params": {"count": 8, "axis": "v"}, "projection": "box",
                         "scale": [0.25, 0.25]}},
    "sweets": {"color": "#d84a3a", "palette": True},
    "cream": {"color": "#e8e2d0", "palette": True},
    "shutter": {"color": "#8a9aa8", "palette": True},
    "wood": {"color": "#8a6a48", "palette": True, "double_sided": True},
    "metal": {"color": "#a0a4a8", "palette": True},
    "red": {"color": "#c0392b", "palette": True},
    "sign": {"color": "#2a6cb4", "class": "emissive", "tag": "sign", "texture": fit("sign")},
    "goods": {"color": "#4a382c", "texture": fit("goods")},
    "mags": {"color": "#c8c8d0", "double_sided": True, "texture": fit("mags")},
    "hang": {"color": "#c8c8d0", "double_sided": True, "texture": fit("hang")},
    "valance": {"color": "#2a6cb4", "double_sided": True, "texture": fit("valance")},
    "board": {"color": "#ece2be", "texture": fit("board")},
    "door": {"color": "#8c6c4e", "tag": "door", "texture": fit("door")},
    "tobacco": {"color": "#d8402f", "texture": fit("tobacco")},
    "card": {"color": "#f0c43c", "texture": fit("card")},
    "side_l": {"color": "#2a6cb4", "tag": "wall", "texture": fit("side_l")},
    "side_r": {"color": "#2a6cb4", "tag": "wall", "texture": fit("side_r")},
    "cat": {"color": "#f4f0e6", "palette": True, "smooth": True},
    "cat_head": {"color": "#f4f0e6", "smooth": True,
                 "texture": {"image": "art/cat_face.png", "projection": "cylindrical",
                             "scale": [0.5341, 0.2], "offset": [0.25, 0.5]}},
}

SHEETS = {"art": {"image": "art/newsstand_sheet.png"},
          "concrete": {"image": "../viaduct_span_16/art/concrete.png"},
          "town_common": {"image": "../town_alley_house_a/art/town_common.png"}}


def shell(far=False):
    """The walls, the shelf wall, the counter, the fascia and the roof."""
    ymid = (Y0 + Y1) / 2
    goods = [{"id": "goods", "face": "back", "material": "goods", "size": [2.5, 0.92],
              "at": [0, r((COUNTER + FASCIA) / 2 + 0.005 - ymid)]}]
    door = [{"id": "door", "face": "front", "material": "door", "size": [0.5, 1.0],
             "at": [-0.5, r(0.62 - ymid)]}]
    n = [span("wall_w", -WX - 0.04, -WX + 0.04, Y0, Y1, ZF, ZB, "enamel", open=["top", "bottom"],
              faces={"left": "side_l", "back": "cream"}),
         span("wall_e", WX - 0.04, WX + 0.04, Y0, Y1, ZF, ZB, "enamel", open=["top", "bottom"],
              faces={"right": "side_r", "back": "cream"}),
         span("shelf_wall", -IN, IN, Y0, Y1, ZS, ZB, "enamel",
              open=["top", "bottom", "left", "right"],
              decals=None if far else goods + door, faces={"back": "goods"} if far else None),
         span("counter", -IN, IN, Y0, COUNTER, ZF, ZS, "enamel",
              open=["bottom", "left", "right", "front"], faces={"top": "laminate"}),
         span("fascia", -1.45, 1.45, FASCIA, Y1, -0.88, -0.70, "enamel", open=["top"],
              faces={"back": "sign"}),
         span("roof", -ROOF_X, ROOF_X, ROOF[0], ROOF[1], ROOF_Z[0], ROOF_Z[1], "roof_edge",
              open=["bottom"] if far else None, faces={"top": "tin"})]
    return n


# ---- level 0 ---------------------------------------------------------------------------
def level0():
    n = [span("plinth", -1.55, 1.55, 0, Y0, -1.05, 0.85, "concrete", open=["bottom"])]
    n += shell()
    # the counter's plates, decals on its front
    counter = next(c for c in n if c["id"] == "counter")
    counter["decals"] = [
        {"id": "plate_tobacco", "face": "back", "material": "tobacco", "size": [0.4, 0.16],
         "at": [-1.05, 0.33]},
        {"id": "plate_card", "face": "back", "material": "card", "size": [0.4, 0.16],
         "at": [1.05, 0.33]}]
    n += [
        cyl("shutter_box", 0.07, 2.58, [0, 1.895, -0.62], "shutter", 5, caps=False,
            rotate=[0, 0, 90]),
        card_z("valance", "valance", -1.64, 1.64, 2.25, ROOF[0], -1.13),
        card_z("hang", "hang", -1.2, 1.2, 1.46, 1.84, -0.66),
        # on the counter: the newspapers, a box of sweets, the lucky cat
        box("news", [0.5, 0.12, 0.36], [-0.88, COUNTER + 0.06, -0.5], "news", open=["bottom"],
            rotate=[0, 6, 0]),
        box("sweets", [0.5, 0.14, 0.3], [0.85, COUNTER + 0.07, -0.55], "sweets", open=["bottom"],
            faces={"top": "news"}),
        {"id": "cat_body", "op": "sphere", "radius": 0.1, "rings": 3, "segments": 4,
         "material": "cat", "transform": {"rotate": [0, 45, 0], "scale": [1, 1.1, 0.9],
                                          "translate": [0.25, COUNTER + 0.115, -0.5]}},
        {"id": "cat_head", "op": "sphere", "radius": 0.085, "rings": 3, "segments": 5,
         "material": "cat_head", "transform": {"translate": [0.25, COUNTER + 0.29, -0.52]}},
        {"id": "cat_ears", "op": "group", "children": [
            {"id": "cat_ear", "op": "cone", "radius": 0.028, "height": 0.05, "segments": 3,
             "material": "cat", "transform": {"translate": [0.055, COUNTER + 0.37, -0.52]}}],
         "modifiers": [{"op": "mirror", "axis": "x", "offset": 0.25}]},
        box("cat_paw", [0.04, 0.09, 0.04], [0.355, COUNTER + 0.25, -0.56], "cat",
            open=["bottom"], rotate=[0, 0, -15]),
        # the magazine racks leaning on the counter
        {"id": "racks", "op": "group", "children": [
            card_z("rack", "mags", 0.22, 1.22, 0.18, 0.82, -0.92, -0.79)],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        # the 号外 board, the ashtray and the stool on the pavement
        card_z("board_front", "board", -1.23, -0.77, 0.0, 0.74, -1.56, -1.43),
        quad("board_back", "wood", [[-1.23, 0.74, -1.41], [-0.77, 0.74, -1.41],
                                    [-0.77, 0.0, -1.28], [-1.23, 0.0, -1.28]]),
        cyl("ash_pole", 0.018, 0.8, [1.25, 0.4, -1.4], "red", 3, caps=False),
        cyl("ash_bowl", 0.1, 0.1, [1.25, 0.85, -1.4], "red", 5),
        cyl("stool_seat", 0.15, 0.05, [0.35, 0.405, -1.25], "red", 5),
        cyl("stool_leg", 0.02, 0.38, [0.35, 0.19, -1.25], "metal", 3, caps=False),
        # the vent on the roof
        cyl("vent_pipe", 0.1, 0.16, [0.9, ROOF[1] + 0.08, 0.3], "shutter", 4, caps=False),
        {"id": "vent_cap", "op": "cone", "radius": 0.17, "height": 0.1, "segments": 4,
         "material": "shutter", "transform": {"translate": [0.9, ROOF[1] + 0.21, 0.3]}},
    ]
    return n


def level1():
    """From 24 m: the shell, with the goods and the door, and the board."""
    return shell() + [card_z("board_front", "board", -1.23, -0.77, 0.0, 0.74, -1.56, -1.43)]


def level2():
    """From 60 m: one box with the goods and the sign on its front, and the roof."""
    ymid = Y1 / 2
    return [span("body", -1.38, 1.38, 0, Y1, ZF, ZB, "enamel", open=["bottom", "top"],
                 faces={"left": "side_l", "right": "side_r"},
                 decals=[{"id": "goods", "face": "back", "material": "goods", "size": [2.5, 0.92],
                          "at": [0, r((COUNTER + FASCIA) / 2 - ymid)]},
                         {"id": "sign", "face": "back", "material": "sign", "size": [2.7, 0.4],
                          "at": [0, r((FASCIA + Y1) / 2 + 0.02 - ymid)]}]),
            span("roof", -ROOF_X, ROOF_X, ROOF[0], ROOF[1], ROOF_Z[0], ROOF_Z[1], "roof_edge",
                 open=["bottom"], faces={"top": "tin"})]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "newsstand",
        "budget": {"triangles": 250},
        "sheets": SHEETS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 120, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def collision():
    def solid(id, x0, x1, y0, y1, z0, z1, open=None):
        return span(id, x0, x1, y0, y1, z0, z1, "solid", open=open)
    n = [solid("plinth", -1.55, 1.55, -0.2, Y0, -1.05, 0.85, open=["bottom"]),
         # the kiosk as one block: the counter's recess (0.95 m high) is no place to stand
         solid("body", -1.38, 1.38, 0.08, 2.4, ZF, ZB, open=["bottom"]),
         # the roof, 2.55 on top, 0.25 thick: a ledge to grab all round
         solid("roof", -ROOF_X, ROOF_X, 2.3, ROOF[1], ROOF_Z[0], ROOF_Z[1]),
         solid("ashtray", 1.13, 1.37, 0.0, 0.9, -1.52, -1.28, open=["bottom"])]
    return {
        "format": "mei-asset", "version": 1, "name": "newsstand_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": {"solid": {"color": "#c8c4b8", "palette": True}},
        "nodes": n,
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("newsstand.asset.json", recipe())
    write("newsstand_col.asset.json", collision())
