#!/usr/bin/env python3
"""Writes art/bus_stop_sheet.png (+ .sheet.json) and bus_stop.asset.json. Run from anywhere."""
import json, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

# ---------------------------------------------------------------- art
W, H = 96, 32
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# cell "disc" (0,0,32,32): the round bus-stop sign, a bus looking out of a blue ring
d.ellipse((0, 0, 31, 31), fill="#1f4e9c")
d.ellipse((3, 3, 28, 28), fill="#f4f1e6")
d.rounded_rectangle((8, 7, 23, 25), 3, fill="#d9453b")
d.rectangle((10, 10, 21, 15), fill="#bfe3f0")
d.line((15, 10, 15, 15), fill="#d9453b")
d.rectangle((11, 8, 20, 8), fill="#f4f1e6")
d.rectangle((10, 19, 12, 20), fill="#f6d94a")
d.rectangle((19, 19, 21, 20), fill="#f6d94a")
d.line((13, 22, 18, 22), fill="#f4f1e6")
d.point([(12, 21), (19, 21)], fill="#f4f1e6")
d.rectangle((9, 25, 11, 27), fill="#2a2a33")
d.rectangle((20, 25, 22, 27), fill="#2a2a33")

# cell "poster" (32,0,32,16): a paper-toy sky, a little bus floating on balloons
ox = 32
for y, c in enumerate(["#6fb8e6"] * 5 + ["#8cc9ec"] * 4 + ["#acd8f0"] * 4 + ["#cde9f4"] * 3):
    d.line((ox, y, ox + 31, y), fill=c)
d.ellipse((ox + 3, 2, ox + 10, 9), fill="#fbe27a")
d.ellipse((ox + 6, 1, ox + 13, 8), fill="#6fb8e6")          # crescent bite
d.ellipse((ox + 18, 1, ox + 27, 4), fill="#f6fbff")
d.ellipse((ox + 5, 9, ox + 13, 12), fill="#f6fbff")
d.rounded_rectangle((ox + 14, 7, ox + 22, 11), 1, fill="#d9453b")
d.rectangle((ox + 15, 8, ox + 21, 9), fill="#bfe3f0")
d.point([(ox + 16, 11), (ox + 20, 11)], fill="#2a2a33")
for bx, col in ((ox + 15, "#f6d94a"), (ox + 18, "#e9798f"), (ox + 21, "#6fd1b0")):
    d.ellipse((bx - 1, 1, bx + 1, 3), fill=col)
    d.line((bx, 4, ox + 18, 7), fill="#f6fbff")
d.polygon([(ox, 15), (ox, 12), (ox + 8, 13), (ox + 16, 14), (ox + 24, 12), (ox + 31, 13), (ox + 31, 15)],
          fill="#5fae6e")

# cell "timetable" (64,0,24,16)
ox = 64
d.rectangle((ox, 0, ox + 23, 15), fill="#f4f1e6")
d.rectangle((ox, 0, ox + 23, 4), fill="#3f8f86")
d.rectangle((ox + 2, 1, ox + 6, 3), fill="#f4f1e6")
for i, y in enumerate((7, 9, 11, 13)):
    d.line((ox + 2, y, ox + 4, y), fill="#2a2a33")
    d.line((ox + 7, y, ox + 7 + (5, 8, 6, 9)[i], y), fill="#8a8f96")
d.rectangle((ox, 0, ox + 23, 15), outline="#2f5f5a")

im.save(os.path.join(HERE, "art", "bus_stop_sheet.png"))
json.dump({"format": "mei-sheet", "version": 1, "cells": {
    "disc": [0, 0, 32, 32], "poster": [32, 0, 32, 16], "timetable": [64, 0, 24, 16]}},
    open(os.path.join(HERE, "art", "bus_stop_sheet.sheet.json"), "w"), indent=2)

# ---------------------------------------------------------------- recipe
def box(i, size, mat, at, **kw):
    n = {"id": i, "op": "box", "size": size, "material": mat, "transform": {"translate": at}}
    n.update(kw)
    return n

materials = {
    "concrete": {"color": "#a9a69c", "texture": {"pattern": "tile", "colors": ["#a9a69c", "#8d8a82", "#b6b3a8"],
                 "params": {"count": 2, "grout": 1}, "projection": "box", "scale": [0.8, 0.8]}},
    "tenji": {"color": "#e8c22e", "texture": {"pattern": "speckle", "colors": ["#e8c22e", "#b8921a"],
              "params": {"density": 0.4}, "projection": "box", "scale": [0.25, 0.25]}},
    "roof": {"color": "#3f8f86", "texture": {"pattern": "stripes", "colors": ["#3f8f86", "#357a72"],
             "params": {"count": 4, "axis": "u"}, "projection": "box", "scale": [0.6, 0.6]}},
    "frame": {"color": "#2f5f5a"},
    "wood": {"color": "#b98962", "texture": {"pattern": "planks", "colors": ["#b98962", "#7d5634", "#a67a52", "#c79a73"],
             "params": {"boards": 4}, "projection": "box", "scale": [0.5, 0.5]}},
    "iron": {"color": "#3b3d46"},
    "poster": {"color": "#e0e0d8", "texture": {"sheet": "sheet", "cell": "poster", "bits": 8, "projection": "fit"}},
    "disc": {"color": "#f4f1e6", "texture": {"sheet": "sheet", "cell": "disc", "bits": 8, "projection": "disc", "axis": "y"}},
    "timetable": {"color": "#f4f1e6", "texture": {"sheet": "sheet", "cell": "timetable", "bits": 8, "projection": "fit"}},
    "pole": {"color": "#e9e5d6"},
    "star": {"color": "#ffe36a", "class": "emissive"},
    "cat": {"color": "#e59a4a"},
    "cat_dark": {"color": "#8a4f24"},
}

nodes = [
    box("slab", [3.4, 0.1, 1.7], "concrete", [0.3, 0.05, 0.15], open=["bottom"]),
    box("tenji", [2.4, 0.02, 0.3], "tenji", [0.0, 0.11, -0.55], open=["bottom"]),
    {"id": "posts", "op": "group", "children": [
        box("post", [0.08, 2.2, 0.08], "frame", [1.05, 1.2, 0.55], open=["bottom"])],
     "modifiers": [{"op": "mirror", "axis": "x"}]},
    box("panel", [2.1, 1.15, 0.06], "frame", [0, 1.3, 0.55]),
    box("poster", [1.9, 0.95, 0.02], "poster", [0, 1.3, 0.51], open=["front"]),
    {"id": "roof", "op": "extrude", "material": "roof",
     "points": [[-0.75, 0], [0.75, 0], [0.75, 0.07], [0.5, 0.13], [0, 0.17], [-0.5, 0.13], [-0.75, 0.07]],
     "depth": 2.5, "transform": {"rotate": [0, 90, 0], "translate": [0, 2.27, 0.1]}},
    # bench
    box("seat", [1.7, 0.05, 0.42], "wood", [0, 0.46, 0.2]),
    box("back", [1.7, 0.32, 0.04], "wood", [0, 0.78, 0.43]),
    {"id": "bench_sides", "op": "group", "children": [
        box("front_leg", [0.05, 0.42, 0.05], "iron", [0.8, 0.21, 0.02], open=["bottom"]),
        box("back_leg", [0.05, 0.9, 0.05], "iron", [0.8, 0.45, 0.45], open=["bottom"]),
        box("arm", [0.04, 0.04, 0.46], "iron", [0.8, 0.62, 0.23])],
     "modifiers": [{"op": "mirror", "axis": "x"}]},
    # sign pole
    {"id": "pole", "op": "cylinder", "radius": 0.035, "height": 2.4, "segments": 8, "caps": False,
     "material": "pole", "transform": {"translate": [1.55, 1.3, -0.1]}},
    {"id": "sign", "op": "cylinder", "radius": 0.24, "height": 0.03, "segments": 12, "material": "disc",
     "transform": {"rotate": [-90, 0, 0], "translate": [1.55, 2.2, -0.12]}},
    box("timetable", [0.42, 0.28, 0.025], "timetable", [1.55, 1.6, -0.12]),
    {"id": "star", "op": "sphere", "radius": 0.07, "rings": 2, "segments": 6, "material": "star",
     "transform": {"translate": [1.55, 2.58, -0.1]}},
    # the cat asleep on the bench
    {"id": "cat_body", "op": "sphere", "radius": 0.2, "rings": 3, "segments": 8, "material": "cat",
     "transform": {"scale": [1.3, 0.7, 1.0], "translate": [-0.45, 0.62, 0.2]}},
    {"id": "cat_head", "op": "sphere", "radius": 0.11, "rings": 3, "segments": 8, "material": "cat",
     "transform": {"translate": [-0.13, 0.64, 0.12]}},
    {"id": "cat_ears", "op": "group", "children": [
        {"id": "ear", "op": "cone", "radius": 0.04, "height": 0.07, "segments": 3, "material": "cat_dark",
         "transform": {"translate": [-0.1, 0.77, 0.06]}}],
     "modifiers": [{"op": "mirror", "axis": "z", "offset": 0.12}]},
    {"id": "cat_tail", "op": "box", "size": [0.3, 0.06, 0.06], "material": "cat_dark",
     "transform": {"rotate": [0, 25, 8], "translate": [-0.78, 0.55, 0.3]}},
    {"id": "cat_nose", "op": "box", "size": [0.025, 0.025, 0.025], "material": "cat_dark",
     "transform": {"translate": [-0.03, 0.63, 0.12]}},
]

recipe = {
    "format": "mei-asset", "version": 1, "name": "bus_stop",
    "budget": {"vertices": 600, "triangles": 450},
    "sheets": {"sheet": {"image": "art/bus_stop_sheet.png"}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
json.dump(recipe, open(os.path.join(HERE, "bus_stop.asset.json"), "w"), indent=1)
