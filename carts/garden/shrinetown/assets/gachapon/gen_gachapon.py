#!/usr/bin/env python3
"""Writes gachapon.asset.json and gachapon_col.asset.json next to this script.

Shrine town's capsule-toy machine: the lab's gachapon (282 triangles) cut to 120. The body, the
roof and the head sign are boxes with the panel, the cat side and the sign baked in as faces and
decals; the capsule window keeps its three-frame animation; the crank is one bar and the yellow
dome stays. Front is -Z. The machine is 0.52 x 0.46 m and 1.34 m tall. Every texture is 4-bit
(the level's palettes, TEXTURES.md).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def post(id_, x, z):
    return {"id": id_, "op": "box", "size": [0.045, 0.4, 0.045], "open": ["top", "bottom"],
            "material": "red", "transform": {"translate": [x, 0.82, z]}}


recipe = {
    "format": "mei-asset", "version": 1, "name": "gachapon",
    "budget": {"vertices": 200, "triangles": 120},
    "sheets": {"gacha": {"image": "art/gacha_sheet.png"}},
    "materials": {
        "red": {"color": "#d8322e", "palette": True},
        "plinth": {"color": "#3a3a42", "palette": True},
        "knob": {"color": "#f4ead2", "palette": True},
        "dome": {"color": "#ffc83a", "palette": True},
        "window": {"color": "#2e4a5c",
                   "texture": {"sheet": "gacha", "frames": ["window_a", "window_b", "window_c"],
                               "ticks": 20, "bits": 4, "projection": "fit"}},
        "panel": {"color": "#d8322e",
                  "texture": {"sheet": "gacha", "cell": "panel", "bits": 4, "projection": "fit"}},
        "header": {"color": "#f4ead2",
                   "texture": {"sheet": "gacha", "cell": "header", "bits": 4, "projection": "fit"}},
        "side": {"color": "#d8322e",
                 "texture": {"sheet": "gacha", "cell": "side", "projection": "fit"}},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "plinth", "op": "box", "size": [0.44, 0.08, 0.38], "open": ["top", "bottom"],
         "material": "plinth", "transform": {"translate": [0, 0.04, 0]}},
        {"id": "body", "op": "box", "size": [0.5, 0.54, 0.44], "open": ["bottom"], "material": "red",
         "faces": {"left": "side", "right": "side"},
         "decals": [{"id": "panel", "face": "back", "material": "panel", "size": [0.4, 0.44],
                     "at": [0, 0]}],
         "transform": {"translate": [0, 0.35, 0]}},
        {"id": "crank", "op": "box", "size": [0.15, 0.036, 0.03], "open": ["front"], "material": "knob",
         "transform": {"rotate": [0, 0, 28], "translate": [0, 0.33, -0.245]}},
        {"id": "window", "op": "box", "size": [0.44, 0.4, 0.38], "open": ["top", "bottom"],
         "material": "window", "transform": {"translate": [0, 0.82, 0]}},
        post("post_lf", -0.23, -0.2), post("post_rf", 0.23, -0.2),
        post("post_lb", -0.23, 0.2), post("post_rb", 0.23, 0.2),
        {"id": "roof", "op": "box", "size": [0.52, 0.12, 0.46], "open": ["bottom"], "material": "red",
         "decals": [{"id": "header", "face": "back", "material": "header", "size": [0.44, 0.1],
                     "at": [0, 0]}],
         "transform": {"translate": [0, 1.08, 0]}},
        {"id": "dome", "op": "lathe", "profile": [[0.19, 1.14], [0.17, 1.26], [0, 1.385]],
         "segments": 8, "caps": False, "material": "dome"},
    ],
}

col = {
    "format": "mei-asset", "version": 1, "name": "gachapon_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [{"id": "body", "op": "box", "size": [0.5, 1.14, 0.44], "material": "solid",
               "open": ["bottom"], "transform": {"translate": [0, 0.57, 0]}}],
}

for name, data in (("gachapon", recipe), ("gachapon_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
