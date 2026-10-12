#!/usr/bin/env python3
"""Cut the lab vegstand (examples/assets/lab/vegstand) to shrine town's 150 triangles.

Run from the repository root: python3 carts/garden/shrinetown/assets/vegstand/cut_vegstand.py
Reads the lab recipe, writes vegstand.asset.json and vegstand_col.asset.json beside this file.
The sheet art/vegstand_sheet.png is the lab's own (a copy).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "..", "..", "..", "examples", "assets", "lab", "vegstand",
                   "vegstand.asset.json")
d = json.load(open(SRC))
d["budget"] = {"vertices": 140, "triangles": 150}
d["lighting"]["ambient"] = 0.5
m = d["materials"]
m["board"]["double_sided"] = True

# A one-sided card with the sign on its front and cardboard on its back.
d["prototypes"]["sign_card"] = {
    "id": "sign_card", "op": "mesh",
    "vertices": [[-0.5, -0.5, -0.006], [0.5, -0.5, -0.006], [0.5, 0.5, -0.006], [-0.5, 0.5, -0.006],
                 [-0.5, -0.5, 0.006], [0.5, -0.5, 0.006], [0.5, 0.5, 0.006], [-0.5, 0.5, 0.006]],
    "faces": [[3, 2, 1, 0], [6, 7, 4, 5]], "face_materials": ["sign", "cardboard"]}
del d["prototypes"]["zaru"]

# Daikon: fewer sides.
dk = d["prototypes"]["daikon"]["children"]
dk[0]["segments"] = 5
dk[1]["segments"] = 4

nodes = [
    {"id": "front_posts", "op": "group", "children": [
        {"id": "post", "op": "box", "size": [0.06, 1.64, 0.06], "open": ["bottom"],
         "material": "post", "transform": {"translate": [0.72, 0.82, -0.27]}}],
     "modifiers": [{"op": "mirror", "axis": "x"}]},
    # The roof is one double-sided sheet of tin; the back is one double-sided board that
    # reaches the ground, in place of the back posts.
    {"id": "roof", "op": "mesh",
     "vertices": [[-0.86, 0, -0.42], [0.86, 0, -0.42], [0.86, 0, 0.42], [-0.86, 0, 0.42]],
     "faces": [[3, 2, 1, 0]], "face_materials": ["tin"],
     "transform": {"rotate": [15.5, 0, 0], "translate": [0, 1.57, -0.01]}},
    {"id": "shelf_low", "op": "box", "size": [1.42, 0.03, 0.52], "open": ["bottom"],
     "material": "shelf", "transform": {"translate": [0, 0.5, 0]}},
    {"id": "shelf_high", "op": "box", "size": [1.42, 0.03, 0.52], "open": ["bottom"],
     "material": "shelf", "transform": {"translate": [0, 0.95, 0]}},
    {"id": "back", "op": "mesh",
     "vertices": [[-0.71, 0, 0], [0.71, 0, 0], [0.71, 1.49, 0], [-0.71, 1.49, 0]],
     "faces": [[3, 2, 1, 0]], "face_materials": ["board"],
     "transform": {"translate": [0, 0, 0.275]}},
    {"id": "sign", "op": "instance", "ref": "sign_card",
     "transform": {"scale": [0.42, 0.28, 1], "rotate": [0, 0, 3], "translate": [0.05, 1.52, -0.37]}},
    {"id": "tomatoes", "op": "cone", "radius": 0.18, "height": 0.1, "segments": 8, "caps": False,
     "material": "tomato", "transform": {"translate": [-0.45, 1.01, -0.02]}},
    {"id": "cucumbers", "op": "cone", "radius": 0.18, "height": 0.08, "segments": 8, "caps": False,
     "material": "cucumber", "transform": {"translate": [0.0, 1.0, 0.0], "rotate": [0, 20, 0]}},
    {"id": "coin_box", "op": "instance", "ref": "coin_tin",
     "transform": {"scale": [0.16, 0.15, 0.13], "rotate": [0, -12, 0], "translate": [0.47, 1.035, 0.02]}},
    {"id": "daikons", "op": "group", "children": [
        {"id": "d1", "op": "instance", "ref": "daikon", "transform": {"translate": [0, 0.05, -0.1]}},
        {"id": "d3", "op": "instance", "ref": "daikon",
         "transform": {"rotate": [0, -6, 0], "translate": [-0.02, 0.12, -0.05]}}],
     "transform": {"translate": [-0.4, 0.51, 0]}},
    {"id": "cabbage", "op": "sphere", "radius": 0.12, "rings": 3, "segments": 6, "material": "cabbage",
     "transform": {"scale": [1, 0.85, 1], "translate": [0.24, 0.615, 0.02]}},
    {"id": "kabocha", "op": "sphere", "radius": 0.13, "rings": 2, "segments": 6, "material": "kabocha",
     "transform": {"scale": [1, 0.72, 1], "translate": [0.5, 0.6, -0.03]}},
]
d["nodes"] = nodes

# Level 1 (30 m): posts, roof, shelves and back; gone from 70 m.
d["lod"] = {"levels": [{"distance": 30, "nodes": [
    nodes[0], nodes[1], nodes[2], nodes[3], nodes[4]]}], "cull": 70}
json.dump(d, open(os.path.join(HERE, "vegstand.asset.json"), "w"), indent=1)


def box(i, size, at, rot=None):
    n = {"id": i, "op": "box", "size": size, "open": ["bottom"], "material": "solid",
         "transform": {"translate": at}}
    if rot:
        n["transform"]["rotate"] = rot
    return n


col = {"format": "mei-asset", "version": 1, "name": "vegstand_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": [
           {"id": "posts", "op": "group", "children": [
               box("post", [0.2, 1.6, 0.2], [0.73, 0.82, -0.27])],
            "modifiers": [{"op": "mirror", "axis": "x"}]},
           box("back", [1.6, 1.45, 0.2], [0, 0.725, 0.3]),
           box("shelf_low", [1.44, 0.22, 0.56], [0, 0.39, -0.02]),
           box("shelf_high", [1.44, 0.2, 0.56], [0, 0.85, -0.02]),
           box("roof", [1.72, 0.2, 0.84], [0, 1.47, -0.01], [15.5, 0, 0])]}
json.dump(col, open(os.path.join(HERE, "vegstand_col.asset.json"), "w"), indent=1)
