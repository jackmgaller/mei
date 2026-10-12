#!/usr/bin/env python3
"""Writes the shrine town's bus stop: art/bus_stop_sheet.png (+ .sheet.json),
bus_stop.asset.json and bus_stop_col.asset.json.

Adapted from the lab model (examples/assets/lab/bus_stop, 354 triangles), whose sheet it reads
(the round sign, the poster, the timetable). Same size and layout: a 3.4 x 1.7 m slab with its
tactile strip, a teal shelter with a lit poster panel, a slatted bench with the orange cat asleep
on it, and the sign pole with its little lamp. The cut: the slab's tiles and tactile strip are
one texture on its top, the bench's legs are two side plates, the sign and timetable are cards,
the roof is a five-point arch, and the cat is a few low spheres.

The roof is a route: it is the first step up from the plaza (spec 4.1, 6.1). Its ridge is 2.44 m
and its edges 2.34 m, 7.6 degrees, walkable; from the bench (0.48) one jump clears it, from the
ground a jump and a grab. The collision follows the arch.

Run: python3 carts/garden/shrinetown/assets/bus_stop/gen_bus_stop.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "bus_stop")
LAB = os.path.join(LABDIR, "art", "bus_stop_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]

FRAME = "#2f5f5a"
ROOF_Y = 2.27                         # the roof's underside at its edges
ROOF_PTS = [[-0.75, 0], [0.75, 0], [0.75, 0.07], [0, 0.17], [-0.75, 0.07]]
ROOF_Z = 0.1                          # the roof's centre line (z)


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def draw_slab_top():
    """64 x 32 over the slab's 3.4 x 1.7 m top (5.3 cm a texel): 40 cm paving tiles, and the
    yellow tactile strip along the kerb (-Z, the bottom rows) from x -1.2 to 1.2."""
    w, h = 64, 32
    img = Image.new("RGBA", (w, h), "#a9a69c")
    d = ImageDraw.Draw(img)
    shades = ["#a9a69c", "#b3b0a6", "#9e9b92"]
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            c = shades[((tx // 8) * 7 + (ty // 8) * 3) % 3]
            d.rectangle([tx, ty, tx + 6, ty + 6], fill=c)
    # tactile strip: slab x -1.4..2.0 -> texel (x + 1.4) / 3.4 * 64; z -0.7..-0.4 -> rows 26..31
    x0 = round((-1.2 + 1.4) / 3.4 * w)
    x1 = round((1.2 + 1.4) / 3.4 * w) - 1
    d.rectangle([x0, 26, x1, 31], fill="#e8c22e")
    for x in range(x0 + 1, x1, 2):
        for y in (27, 29):
            d.point((x, y), fill="#b8921a")
    return img


def draw_panel(src):
    """36 x 20: the poster in its teal frame (the panel is 2.1 x 1.15 m)."""
    img = Image.new("RGBA", (36, 20), FRAME)
    img.paste(lab(src, "poster"), (2, 2))
    return img


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (128, 52), (0, 0, 0, 0))
    cells = {}

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("slab_top", draw_slab_top(), 0, 0)
    put("disc", lab(src, "disc"), 64, 0)
    put("timetable", lab(src, "timetable"), 96, 0)
    put("panel", draw_panel(src), 0, 32)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "bus_stop_sheet.png"))
    with open(os.path.join(HERE, "art", "bus_stop_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v, 4)


def box(id, size, at, material, open=None, faces=None, rotate=None, decals=None):
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


def quad(id, material, corners):
    """One polygon (corners counter-clockwise seen from its front)."""
    return {"id": id, "op": "mesh", "material": material,
            "vertices": [[r(c) for c in p] for p in corners], "faces": [list(range(len(corners)))]}


def sphere(id, radius, rings, segments, at, material, scale=None):
    t = {}
    if scale:
        t["scale"] = scale
    t["translate"] = [r(a) for a in at]
    return {"id": id, "op": "sphere", "radius": radius, "rings": rings, "segments": segments,
            "material": material, "transform": t}


def fit(cell, bits=4):               # 4-bit: no 8-bit textures in shrine town (TEXTURES.md)
    t = {"sheet": "art", "cell": cell, "projection": "fit"}
    if bits == 8:
        t["bits"] = 8
    return t


MATERIALS = {
    "slab_top": {"color": "#a9a69c", "tag": "floor", "texture": fit("slab_top", bits=4)},
    "kerb": {"color": "#a8a69e", "palette": True},
    "roof": {"color": "#3f8f86", "tag": "roof",
             "texture": {"pattern": "stripes", "size": 16, "colors": ["#3f8f86", "#357a72"],
                         "params": {"count": 4, "axis": "u"}, "projection": "box",
                         "scale": [0.5, 0.5]}},
    "frame": {"color": FRAME, "palette": True},
    "wood": {"color": "#b98962", "tag": "bench",
             "texture": {"pattern": "planks", "size": 16,
                         "colors": ["#b98962", "#7d5634", "#a67a52", "#c79a73"],
                         "params": {"boards": 4}, "projection": "box", "scale": [0.5, 0.5]}},
    "iron": {"color": "#3b3d46", "palette": True, "double_sided": True},
    "pole": {"color": "#e9e5d6", "palette": True},
    "panel": {"color": "#e0e0d8", "class": "emissive", "tag": "sign", "texture": fit("panel")},
    "disc": {"color": "#f4f1e6", "double_sided": True, "texture": fit("disc")},
    "timetable": {"color": "#f4f1e6", "double_sided": True, "texture": fit("timetable")},
    "lamp": {"color": "#ffe36a", "class": "emissive", "tag": "lantern"},
    "cat": {"color": "#e59a4a", "palette": True},
    "cat_dark": {"color": "#8a4f24", "palette": True},
}


def roof_node():
    return {"id": "roof", "op": "extrude", "material": "roof", "points": ROOF_PTS, "depth": 2.5,
            "transform": {"rotate": [0, 90, 0], "translate": [0, ROOF_Y, ROOF_Z]}}


def bench_end(id, x):
    # side profile in (z, y): under the seat, up the back, the arm sloping down to the front
    p = [(0.0, 0.0), (0.45, 0.0), (0.45, 0.94), (0.4, 0.94), (0.0, 0.62)]
    return quad(id, "iron", [[x, y, z] for z, y in p] if x > 0 else
                [[x, y, z] for z, y in reversed(p)])


# ---- level 0 ---------------------------------------------------------------------------
def level0():
    n = [box("slab", [3.4, 0.1, 1.7], [0.3, 0.05, 0.15], "kerb", open=["bottom"],
             faces={"top": "slab_top"}),
         {"id": "posts", "op": "group", "children": [
             box("post", [0.08, ROOF_Y + 0.08 - 0.1, 0.14], [1.05, (ROOF_Y + 0.08 + 0.1) / 2, 0.55],
                 "frame", open=["top", "bottom"])],
          "modifiers": [{"op": "mirror", "axis": "x"}]},
         box("panel", [2.1, 1.15, 0.06], [0, 1.3, 0.55], "frame", open=["bottom"],
             faces={"back": "panel"}),
         roof_node(),
         # the bench
         box("seat", [1.7, 0.05, 0.42], [0, 0.46, 0.2], "wood", open=["bottom"]),
         box("back", [1.7, 0.32, 0.04], [0, 0.78, 0.43], "wood", open=["bottom"]),
         bench_end("bench_end_e", 0.8),
         bench_end("bench_end_w", -0.8),
         # the sign pole, its round sign, timetable and lamp
         {"id": "pole", "op": "cylinder", "radius": 0.035, "height": 2.4, "segments": 4,
          "caps": False, "material": "pole", "transform": {"translate": [1.55, 1.3, -0.1]}},
         quad("sign", "disc", [[1.31, 2.44, -0.14], [1.79, 2.44, -0.14],
                                [1.79, 1.96, -0.14], [1.31, 1.96, -0.14]]),
         quad("timetable", "timetable", [[1.34, 1.74, -0.14], [1.76, 1.74, -0.14],
                                          [1.76, 1.46, -0.14], [1.34, 1.46, -0.14]]),
         sphere("lamp", 0.07, 2, 4, [1.55, 2.57, -0.1], "lamp"),
         # the cat asleep on the bench
         sphere("cat_body", 0.2, 3, 5, [-0.45, 0.6, 0.2], "cat", scale=[1.3, 0.7, 1.0]),
         sphere("cat_head", 0.11, 3, 4, [-0.15, 0.64, 0.12], "cat"),
         {"id": "cat_ears", "op": "group", "children": [
             {"id": "ear", "op": "cone", "radius": 0.04, "height": 0.07, "segments": 3,
              "material": "cat_dark", "transform": {"translate": [-0.12, 0.76, 0.06]}}],
          "modifiers": [{"op": "mirror", "axis": "z", "offset": 0.12}]},
         {"id": "cat_tail", "op": "cone", "radius": 0.035, "height": 0.34, "segments": 3,
          "material": "cat_dark",
          "transform": {"rotate": [0, 25, 80], "translate": [-0.82, 0.53, 0.28]}}]
    return n


def tall_panel(y0):
    """The panel and its posts as one frame from y0 up to the roof, the poster a decal at the
    panel's height (1.3 m)."""
    h = ROOF_Y - y0
    return box("panel", [2.2, h, 0.1], [0, y0 + h / 2, 0.55], "frame", open=["bottom", "top"],
               decals=[{"id": "poster", "face": "back", "material": "panel", "size": [2.1, 1.15],
                        "at": [0, r(1.3 - (y0 + h / 2))]}])


def level1():
    """From 24 m: the slab, the panel, the roof, the bench as a block, the pole and sign."""
    return [box("slab", [3.4, 0.1, 1.7], [0.3, 0.05, 0.15], "kerb", open=["bottom"],
                faces={"top": "slab_top"}),
            tall_panel(0.1),
            roof_node(),
            box("bench", [1.7, 0.5, 0.45], [0, 0.35, 0.22], "wood", open=["bottom"]),
            {"id": "pole", "op": "cylinder", "radius": 0.04, "height": 2.4, "segments": 3,
             "caps": False, "material": "pole", "transform": {"translate": [1.55, 1.3, -0.1]}},
            quad("sign", "disc", [[1.31, 2.44, -0.14], [1.79, 2.44, -0.14],
                                   [1.79, 1.96, -0.14], [1.31, 1.96, -0.14]])]


def level2():
    """From 60 m: the panel's frame with its poster, and the roof."""
    return [tall_panel(0.0),
            box("roof", [2.5, 0.12, 1.5], [0, ROOF_Y + 0.06, ROOF_Z], "roof")]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "bus_stop",
        "budget": {"triangles": 150},
        "sheets": {"art": {"image": "art/bus_stop_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 120, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               "solid", open=open)


def collision():
    # the roof: the render's arch on top, 0.2 m thick at its edges
    pts = [[-0.75, -0.13], [0.75, -0.13], [0.75, 0.07], [0, 0.17], [-0.75, 0.07]]
    n = [solid("slab", -1.4, 2.0, -0.2, 0.1, -0.7, 1.0, open=["bottom"]),
         solid("panel", -1.1, 1.1, 0.08, 1.9, 0.45, 0.65, open=["bottom"]),
         solid("bench", -0.85, 0.85, 0.08, 0.48, -0.01, 0.47, open=["bottom"]),
         solid("pole", 1.45, 1.65, 0.08, 2.5, -0.2, 0.0, open=["bottom"]),
         {"id": "roof", "op": "extrude", "material": "solid", "points": pts, "depth": 2.5,
          "transform": {"rotate": [0, 90, 0], "translate": [0, ROOF_Y, ROOF_Z]}}]
    return {
        "format": "mei-asset", "version": 1, "name": "bus_stop_col",
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
    write("bus_stop.asset.json", recipe())
    write("bus_stop_col.asset.json", collision())
