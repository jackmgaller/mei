#!/usr/bin/env python3
"""Writes hokora.asset.json and hokora_col.asset.json next to this script.

Shrine town's roadside hokora: the lab's hokora (300 triangles, examples/assets/lab/hokora) cut
to 150. The stone base (two slabs), the wooden body with its lattice door baked in as a decal,
the tiled gable roof as one triangular prism (gable ends in wood), the ridge and gold finial,
the shimenawa with its shide, the little red torii and the two fox guardians (a pedestal, a
cone body, a snout and a red bib each) stay. The step, the moss patch, the fox ears and tails
and the torii's shimaki are gone. Front is -Z; 1.1 x 1.3 m, 1.1 m tall.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def quad(id_, mat, pts):
    return {"id": id_, "op": "mesh", "material": mat, "vertices": pts, "faces": [[0, 1, 2, 3]]}


def box(id_, size, at, mat, open_=("bottom",), **kw):
    n = {"id": id_, "op": "box", "size": size, "material": mat, "open": list(open_),
         "transform": {"translate": at}}
    n.update(kw)
    return n


def fox():
    return {"id": "fox", "op": "group", "children": [
        box("ped", [0.17, 0.12, 0.17], [0, 0.06, 0], "stone"),
        {"id": "body", "op": "cone", "radius": 0.075, "height": 0.28, "segments": 4,
         "caps": False, "material": "stone", "transform": {"translate": [0, 0.26, 0]}},
        {"id": "snout", "op": "cone", "radius": 0.045, "height": 0.1, "segments": 4,
         "material": "stone", "transform": {"rotate": [-90, 0, 0],
                                            "translate": [0, 0.33, -0.07]}},
        quad("bib", "bib", [[-0.05, 0.27, -0.06], [0.05, 0.27, -0.06],
                            [0.04, 0.17, -0.07], [-0.04, 0.17, -0.07]]),
    ], "transform": {"translate": [0.42, 0.12, -0.4]}}


recipe = {
    "format": "mei-asset", "version": 1, "name": "hokora",
    "budget": {"vertices": 260, "triangles": 150},
    "materials": {
        "stone": {"color": "#8d8f8c", "tag": "stone",
                  "texture": {"pattern": "speckle", "colors": ["#8f918d", "#6c6f6d", "#a9aba5"],
                              "params": {"density": 0.22, "seed": 3}, "projection": "box",
                              "scale": [0.6, 0.6]}},
        "wood": {"color": "#8a6444",
                 "texture": {"pattern": "planks",
                             "colors": ["#8b6544", "#4c321f", "#7a5538", "#9b7552"],
                             "params": {"boards": 4}, "projection": "box",
                             "scale": [0.5, 0.5]}},
        "door": {"color": "#4a2f20",
                 "texture": {"pattern": "lattice", "colors": ["#9a7048", "#1d130d"],
                             "params": {"count": 4, "bar": 1}, "projection": "fit"}},
        "tile": {"color": "#4b5560",
                 "texture": {"pattern": "brick", "colors": ["#59656f", "#2c343b", "#4a545d"],
                             "params": {"courses": 4, "bricks": 4, "bond": 0.5},
                             "projection": "box", "scale": [0.28, 0.28]}},
        "ridge": {"color": "#2f373d", "palette": True},
        "red": {"color": "#c93a2b", "palette": True},
        "rope": {"color": "#d9c691", "palette": True},
        "paper": {"color": "#f3f1e8", "palette": True, "double_sided": True},
        "bib": {"color": "#d63a2a", "palette": True, "double_sided": True},
        "gold": {"color": "#d9b04a", "palette": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        box("base_low", [1.1, 0.12, 1.3], [0, 0.06, 0.05], "stone"),
        box("base_high", [0.74, 0.1, 0.62], [0, 0.17, 0.08], "stone"),
        box("body", [0.52, 0.62, 0.46], [0, 0.53, 0.08], "wood", ("bottom", "top"),
            decals=[{"id": "door", "face": "back", "material": "door", "size": [0.34, 0.44],
                     "at": [0, -0.06]}]),
        {"id": "roof", "op": "extrude", "material": "tile",
         "points": [[-0.45, 0.0], [0.45, 0.0], [0.0, 0.2]], "depth": 1.0,
         "faces": {"front": "wood", "back": "wood"},
         "transform": {"rotate": [0, 90, 0], "translate": [0, 0.84, 0.08]}},
        box("ridge", [1.04, 0.05, 0.08], [0, 1.06, 0.08], "ridge"),
        {"id": "finial", "op": "cone", "radius": 0.04, "height": 0.08, "segments": 4,
         "material": "gold", "transform": {"translate": [0, 1.13, 0.08]}},
        {"id": "rope", "op": "cylinder", "radius": 0.014, "height": 0.52, "segments": 3,
         "caps": False, "material": "rope",
         "transform": {"rotate": [0, 0, 90], "translate": [0, 0.78, -0.17]}},
        {"id": "shide", "op": "group", "children": [
            quad("s1", "paper", [[-0.15, 0.77, -0.19], [-0.09, 0.77, -0.19],
                                 [-0.1, 0.65, -0.19], [-0.14, 0.65, -0.19]]),
            quad("s2", "paper", [[0.09, 0.77, -0.19], [0.15, 0.77, -0.19],
                                 [0.14, 0.65, -0.19], [0.1, 0.65, -0.19]]),
        ]},
        {"id": "torii", "op": "group", "children": [
            box("post", [0.05, 0.5, 0.05], [0.26, 0.37, 0], "red", ("top", "bottom")),
        ], "modifiers": [{"op": "mirror", "axis": "x"}],
         "transform": {"translate": [0, 0, -0.5]}},
        box("kasagi", [0.7, 0.04, 0.07], [0, 0.64, -0.5], "ridge"),
        box("nuki", [0.46, 0.035, 0.035], [0, 0.5, -0.5], "red", ("top", "bottom")),
        {"id": "foxes", "op": "group", "children": [fox()],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
    ],
}

col = {
    "format": "mei-asset", "version": 1, "name": "hokora_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        box("base", [1.1, 0.12, 1.3], [0, 0.06, 0.05], "solid"),
        box("shrine", [1.0, 0.9, 0.9], [0, 0.57, 0.08], "solid"),
    ],
}

for name, data in (("hokora", recipe), ("hokora_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
