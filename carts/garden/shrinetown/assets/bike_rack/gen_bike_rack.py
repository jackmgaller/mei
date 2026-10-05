#!/usr/bin/env python3
"""Writes the shrine town's bicycle shelter: art/bike_rack_sheet.png (+ .sheet.json),
bike_rack.asset.json and bike_rack_col.asset.json.

Adapted from the lab model (examples/assets/lab/bike_rack, 334 triangles), whose 駐輪場 sign it
reads. Same size: a 3.2 x 2.1 m concrete pad under a green corrugated roof on four posts, falling
8 degrees to the back, with a low rail of wheel stands along the front. The cut: the lab's four
bicycles are not modelled here. The world parks the town's `mamachari` in the five slots
(x -1.2, -0.6, 0, 0.6, 1.2; z 0; yaw 0, front wheel in the stands; y 0.1 on the pad), and the
mamachari is culled at 40 m, so this asset's far level (from 40 m) carries the parked bicycles
as two crossed cutout cards instead.

The roof is a step: its back eave is 1.98 m up, its front 2.30, so the player jumps onto the
back and walks up 8 degrees; the collision's roof is the render's tilted slab, 0.2 m thick.

Run: python3 carts/garden/shrinetown/assets/bike_rack/gen_bike_rack.py   (needs Pillow)
"""
import json
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB_SIGN = os.path.join(REPO, "examples", "assets", "lab", "bike_rack", "art", "sign.png")

PAD = 0.1                    # the pad's top
TILT = 8.0                   # the roof's fall to the back (+Z), degrees
ROOF_T = 0.06
ROOF_W, ROOF_D = 3.4, 2.3
ROOF_TOP = 2.14              # the roof's top at z 0
PX, PZ = 1.5, 0.95           # posts at (+-PX, +-PZ)
SLOTS = [-1.2, -0.6, 0.0, 0.6, 1.2]
FINS = [-1.5, -0.9, -0.3, 0.3, 0.9, 1.5]
BIKES = ["#7fcab6", "#d0402e", "#e8b830", "#2e4f9c", "#e87aa4"]


def roof_top(z):
    return ROOF_TOP - z * math.tan(math.radians(TILT))


def roof_under(z):
    return roof_top(z) - ROOF_T / math.cos(math.radians(TILT))


# ---- art -------------------------------------------------------------------------------
def draw_bikes_front():
    """64 x 16, holes around: the five parked bicycles seen from the front (head-on), for the
    far level: tyre, fork, handlebar and basket."""
    im = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, col in enumerate(BIKES):
        cx = 6 + i * 13
        d.rectangle([cx, 9, cx + 1, 15], fill="#2b2a30")          # the tyre, edge on
        d.rectangle([cx, 4, cx + 1, 8], fill=col)                 # the fork and head tube
        d.rectangle([cx - 4, 3, cx + 5, 3], fill="#c9ced6")       # the handlebar
        d.rectangle([cx - 2, 5, cx + 3, 8], fill="#cfd3da")       # the basket
        d.rectangle([cx - 1, 6, cx + 2, 7], fill="#8a9098")
    return im


def draw_bikes_side():
    """64 x 16, holes around: the row seen from the side, wheels overlapping."""
    im = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for cx in (12, 52):
        d.ellipse([cx - 9, 0 + 6, cx + 9, 15], outline="#2b2a30", width=2)
    d.line([12, 11, 30, 11, 42, 4, 30, 11], fill=BIKES[0], width=2)
    d.line([24, 4, 30, 11], fill=BIKES[0], width=2)
    d.line([42, 4, 52, 11], fill=BIKES[0], width=2)
    d.rectangle([20, 2, 28, 3], fill="#4a3426")                   # the saddle
    d.rectangle([44, 1, 56, 6], fill="#cfd3da")                   # the basket
    return im


def draw_pictogram():
    """16 x 16: the blue bicycle-parking plate, a white bicycle on blue."""
    im = Image.new("RGBA", (16, 16), "#2e5fae")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 15], outline="#f2efe6")
    for cx in (4, 11):
        d.ellipse([cx - 3, 7, cx + 3, 13], outline="#f2efe6")
    d.line([4, 10, 7, 10, 10, 6, 7, 10], fill="#f2efe6")
    d.line([6, 5, 7, 10], fill="#f2efe6")
    d.line([10, 6, 11, 10], fill="#f2efe6")
    d.line([5, 5, 7, 5], fill="#f2efe6")
    d.line([9, 4, 11, 4], fill="#f2efe6")
    return im


def draw_bikes():
    """64 x 48: the far level's two cards (rows 0-15 and 16-31) and the parking plate
    (row 32, the first 16 texels), one texture mapped by hand UVs."""
    im = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
    im.paste(draw_bikes_front(), (0, 0))
    im.paste(draw_bikes_side(), (0, 16))
    im.paste(draw_pictogram(), (0, 32))
    return im


def draw_art():
    sheet = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    cells = {}

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("sign", Image.open(LAB_SIGN).convert("RGBA"), 0, 0)
    put("bikes", draw_bikes(), 0, 16)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "bike_rack_sheet.png"))
    with open(os.path.join(HERE, "art", "bike_rack_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v, 4)


def box(id, size, at, material, open=None, faces=None, rotate=None):
    n = {"id": id, "op": "box", "size": [r(s) for s in size], "material": material}
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    t = {}
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n["transform"] = t
    return n


def span(id, x0, x1, y0, y1, z0, z1, material, **kw):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               material, **kw)


def quad(id, material, corners, uvs=None):
    n = {"id": id, "op": "mesh", "material": material,
         "vertices": [[r(c) for c in p] for p in corners], "faces": [[0, 1, 2, 3]]}
    if uvs:
        n["uvs"] = uvs
    return n


def rows(v0, v1, u1=1.0):
    """Hand UVs for a quad given top-left, top-right, bottom-right, bottom-left: texture rows
    v0..v1 (in texels of the 48-row cell), u 0..u1."""
    a, b = r(v0 / 48), r(v1 / 48)
    return [[0, a], [u1, a], [u1, b], [0, b]]


def plate():
    """The parking plate on the front west post, 3.5 cm proud of it, facing the front."""
    x, z = -PX, -PZ - 0.075
    return quad("plate", "bikes", [[x - 0.13, 1.83, z], [x + 0.13, 1.83, z],
                                   [x + 0.13, 1.57, z], [x - 0.13, 1.57, z]],
                uvs=rows(32, 48, 0.25))


MATERIALS = {
    "concrete": {"color": "#b4b0a6", "tag": "floor",
                 "texture": {"sheet": "concrete", "cell": "wall", "projection": "box",
                             "scale": [4.0, 2.0]}},
    "roof": {"color": "#4a9d78", "tag": "roof",
             "texture": {"pattern": "stripes", "size": 16, "colors": ["#58b08a", "#3f8c6a"],
                         "params": {"count": 8, "axis": "u"}, "projection": "box",
                         "scale": [1.0, 1.0]}},
    "steel": {"color": "#7d858c", "palette": True},
    "fin": {"color": "#8c949a", "palette": True, "double_sided": True},
    "post": {"color": "#5f6a70", "palette": True, "double_sided": True},
    "sign": {"color": "#185c46", "tag": "sign", "texture": {"sheet": "art", "cell": "sign",
                                                            "bits": 8, "projection": "fit"}},
    "bikes": {"color": "#7fcab6", "double_sided": True,
              "texture": {"sheet": "art", "cell": "bikes", "projection": "fit"}},
}

SHEETS = {"art": {"image": "art/bike_rack_sheet.png"},
          "concrete": {"image": "../viaduct_span_16/art/concrete.png"}}


def roof_node(open=None):
    return box("roof", [ROOF_W, ROOF_T, ROOF_D], [0, ROOF_TOP - ROOF_T / 2, 0], "roof",
               open=open, rotate=[TILT, 0, 0])


def posts(kind="box"):
    n = []
    for side, z in (("front", -PZ), ("back", PZ)):
        top = roof_under(z) + 0.03
        for ew, x in (("w", -PX), ("e", PX)):
            id = f"post_{side}_{ew}"
            if kind == "box":
                n.append(span(id, x - 0.04, x + 0.04, PAD, top, z - 0.04, z + 0.04, "post",
                              open=["top", "bottom"]))
            elif kind == "cyl":
                n.append({"id": id, "op": "cylinder", "radius": 0.05, "height": r(top),
                          "segments": 3, "caps": False, "material": "post",
                          "transform": {"translate": [x, r(top / 2), z]}})
            else:  # a card facing the front, double-sided
                n.append(quad(id, "post", [[x - 0.05, top, z], [x + 0.05, top, z],
                                           [x + 0.05, 0, z], [x - 0.05, 0, z]]))
    return n


def sign_node():
    # on the front beam's face, sunk 5 mm into it
    return span("sign", -0.6, 0.6, 1.86, 2.16, -PZ - 0.1, -PZ - 0.035, "steel",
                faces={"back": "sign"})


# ---- level 0 ---------------------------------------------------------------------------
def level0():
    n = [span("pad", -1.6, 1.6, 0, PAD, -1.05, 1.05, "concrete", open=["bottom"]),
         span("rail", -1.55, 1.55, PAD, PAD + 0.1, -0.535, -0.465, "steel", open=["bottom"])]
    # the wheel stands: plates across the rail, between the slots
    for i, x in enumerate(FINS):
        n.append(quad(f"stand_{i}", "fin", [[x, PAD, -0.8], [x, PAD, -0.2],
                                            [x, 0.48, -0.42], [x, 0.48, -0.62]]))
    n += posts("box")
    for side, z in (("front", -PZ), ("back", PZ)):
        y = roof_under(z) - 0.06
        n.append(span(f"beam_{side}", -PX + 0.04, PX - 0.04, y - 0.04, y + 0.04, z - 0.04,
                      z + 0.04, "post", open=["left", "right"]))
    n += [roof_node(), sign_node(), plate()]
    return n


def level1():
    """From 24 m: the roof, the posts and the sign."""
    return [roof_node(), sign_node()] + posts("cyl")


def level2():
    """From 40 m, where the parked mamachari are culled: the roof, the posts as cards, and the
    bicycles as two crossed cards."""
    hb = 0.95
    return [roof_node(open=["bottom"])] + posts("card") + [
        quad("bikes_front", "bikes", [[-1.55, hb + PAD, -0.3], [1.55, hb + PAD, -0.3],
                                       [1.55, PAD, -0.3], [-1.55, PAD, -0.3]], uvs=rows(0, 16)),
        quad("bikes_side", "bikes", [[0, hb + PAD, -0.9], [0, hb + PAD, 0.9],
                                      [0, PAD, 0.9], [0, PAD, -0.9]], uvs=rows(16, 32))]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "bike_rack",
        "budget": {"triangles": 150},
        "sheets": SHEETS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 40, "nodes": level2()}], "cull": 100, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def collision():
    def solid(id, x0, x1, y0, y1, z0, z1, open=None):
        return span(id, x0, x1, y0, y1, z0, z1, "solid", open=open)
    n = [solid("pad", -1.6, 1.6, -0.2, PAD, -1.05, 1.05, open=["bottom"]),
         solid("stands", -1.55, 1.55, 0.08, 0.5, -0.8, -0.2, open=["bottom"])]
    for side, z in (("front", -PZ), ("back", PZ)):
        top = roof_under(z) + 0.03
        for ew, x in (("w", -PX), ("e", PX)):
            cx, cz = x - math.copysign(0.02, x), z - math.copysign(0.02, z)
            n.append(solid(f"post_{side}_{ew}", cx - 0.1, cx + 0.1, 0.08, top, cz - 0.1, cz + 0.1,
                           open=["bottom"]))
    # the roof: the render's top, 0.2 m thick
    n.append(box("roof", [ROOF_W, 0.2, ROOF_D], [0, ROOF_TOP - 0.1, 0], "solid",
                 rotate=[TILT, 0, 0]))
    return {
        "format": "mei-asset", "version": 1, "name": "bike_rack_col",
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
    write("bike_rack.asset.json", recipe())
    write("bike_rack_col.asset.json", collision())
