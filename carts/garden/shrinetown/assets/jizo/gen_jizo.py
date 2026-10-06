#!/usr/bin/env python3
"""Writes jizo.asset.json and jizo_col.asset.json next to this script.

Shrine town's roadside jizo: the lab's jizo (382 triangles, examples/assets/lab/jizo) cut to
150. Two stone steps, an 8-sided robe, the red bib as a flared collar and a front flap, the
carved-face head and the red cap with its bobble stay; the sleeves, hands, cup, pebbles and
moss are gone, and the staff, its ring, the jewel and the pinwheel are single thin parts. The
art/ PNGs (face, staff ring, pinwheel) are the lab's. Front is -Z; 0.6 x 0.5 m, 1.1 m tall.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SPECKLE = ["#9a988a", "#8c8a7e", "#a6a496", "#7e8c6c"]


def quad(id_, mat, pts):
    return {"id": id_, "op": "mesh", "material": mat, "vertices": pts, "faces": [[0, 3, 2, 1]]}


recipe = {
    "format": "mei-asset", "version": 1, "name": "jizo",
    "budget": {"vertices": 200, "triangles": 150},
    "materials": {
        "stone": {"color": "#989688", "tag": "stone",
                  "texture": {"pattern": "speckle", "size": 16, "colors": SPECKLE,
                              "params": {"density": 0.32, "seed": 5}, "projection": "box",
                              "scale": [0.5, 0.5]}},
        "robe": {"color": "#989688", "smooth": True,
                 "texture": {"pattern": "speckle", "size": 32, "colors": SPECKLE,
                             "params": {"density": 0.28, "seed": 11},
                             "projection": "cylindrical", "scale": [0.5, 0.5]}},
        "face": {"color": "#989688", "smooth": True,
                 "texture": {"image": "art/jizo_face.png", "projection": "cylindrical",
                             "scale": [0.8796, 0.34], "offset": [0.25, 0.5]}},
        "wool": {"color": "#c8352c", "palette": True, "smooth": True},
        "bib": {"color": "#d63a30", "palette": True, "double_sided": True},
        "bobble": {"color": "#f0e6d2", "palette": True},
        "wood": {"color": "#7a5a3c", "palette": True},
        "gold": {"color": "#d4b24e", "palette": True},
        "ring": {"color": "#d4b24e", "double_sided": True,
                 "texture": {"image": "art/jizo_ring.png", "projection": "fit"}},
        "pinwheel": {"color": "#d04040", "double_sided": True,
                     "texture": {"image": "art/jizo_pinwheel.png", "projection": "fit"}},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    # a small prop: no levels, culled (a world's lod.assets may say sooner)
    "lod": {"cull": 50},
    "nodes": [
        {"id": "step_low", "op": "box", "size": [0.6, 0.12, 0.5], "open": ["bottom"],
         "material": "stone", "transform": {"translate": [0, 0.06, 0]}},
        {"id": "step_high", "op": "box", "size": [0.4, 0.08, 0.34], "open": ["bottom"],
         "material": "stone", "transform": {"translate": [0, 0.16, 0]}},
        {"id": "robe", "op": "lathe", "segments": 8, "caps": False, "material": "robe",
         "profile": [[0.2, 0.0], [0.15, 0.25], [0.09, 0.5]],
         "transform": {"translate": [0, 0.2, 0]}},
        {"id": "bib_ring", "op": "lathe", "segments": 8, "caps": False, "material": "bib",
         "profile": [[0.16, 0.0], [0.1, 0.08]], "transform": {"translate": [0, 0.66, 0]}},
        quad("bib_flap", "bib", [[-0.09, 0.7, -0.14], [0.09, 0.7, -0.14],
                                 [0.07, 0.52, -0.17], [-0.07, 0.52, -0.17]]),
        {"id": "head", "op": "sphere", "radius": 0.14, "rings": 3, "segments": 8,
         "material": "face", "transform": {"translate": [0, 0.84, 0], "scale": [1, 1.04, 1]}},
        {"id": "cap", "op": "cone", "radius": 0.155, "height": 0.18, "segments": 8,
         "material": "wool", "transform": {"translate": [0, 0.97, 0]}},
        {"id": "bobble", "op": "sphere", "radius": 0.03, "rings": 2, "segments": 4,
         "material": "bobble", "transform": {"translate": [0, 1.08, 0]}},
        {"id": "staff", "op": "cylinder", "radius": 0.014, "height": 0.78, "segments": 3,
         "caps": False, "material": "wood", "transform": {"translate": [-0.17, 0.51, -0.2]}},
        quad("staff_ring", "ring", [[-0.22, 0.9, -0.2], [-0.12, 0.9, -0.2],
                                    [-0.12, 1.0, -0.2], [-0.22, 1.0, -0.2]]),
        {"id": "jewel", "op": "sphere", "radius": 0.035, "rings": 2, "segments": 4,
         "material": "gold", "transform": {"translate": [0.15, 0.56, -0.14]}},
        {"id": "pinwheel_stick", "op": "cylinder", "radius": 0.007, "height": 0.34,
         "segments": 3, "caps": False, "material": "wood",
         "transform": {"translate": [0.25, 0.29, -0.24]}},
        quad("pinwheel", "pinwheel", [[0.19, 0.38, -0.25], [0.31, 0.38, -0.25],
                                      [0.31, 0.5, -0.25], [0.19, 0.5, -0.25]]),
    ],
}

col = {
    "format": "mei-asset", "version": 1, "name": "jizo_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "steps", "op": "box", "size": [0.6, 0.2, 0.5], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [0, 0.1, 0]}},
        {"id": "body", "op": "box", "size": [0.4, 0.9, 0.34], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [0, 0.65, 0]}},
    ],
}

for name, data in (("jizo", recipe), ("jizo_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
