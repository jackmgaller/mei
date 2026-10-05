#!/usr/bin/env python3
"""Writes town_road_signs.asset.json: two sign poles for the front road and the alleys.

Run from anywhere. The art is the sign sheet, ../town_signs_sheet/town_signs.png (drawn by
../town_signs_sheet/draw_signs.py). Origin: the middle of the pair at the foot, the signs face -Z.
West pole: 止まれ (stop). East pole: 30 km/h above a school-zone diamond.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = "../town_signs_sheet/town_signs.png"

SIDES = ["left", "right", "top", "bottom"]   # a plate is its two faces; its 2 cm edge is not drawn


def tex(cell):
    return {"color": "#f4f1e6", "texture": {"sheet": "signs", "cell": cell, "projection": "fit"}}


materials = {
    "tomare": tex("tomare"),
    "speed30": tex("speed30"),
    "school": tex("school"),
    "steel": {"color": "#a8a69e", "palette": True},   # poles and plate backs
}


def plate(i, w, h, cell, at):
    return {"id": i, "op": "box", "size": [w, h, 0.03], "material": "steel", "open": SIDES,
            "faces": {"back": cell}, "transform": {"translate": at}}


def pole(i, x, height):
    return {"id": i, "op": "box", "size": [0.07, height, 0.07], "material": "steel",
            "open": ["top", "bottom"], "transform": {"translate": [x, height / 2 - 0.01, 0.055]}}


nodes = [
    pole("pole_stop", -0.9, 2.5),
    {"id": "stop", "op": "extrude", "material": "steel", "faces": {"back": "tomare"}, "depth": 0.03,
     "points": [[-0.45, 0.39], [0.45, 0.39], [0.0, -0.39]],
     "transform": {"translate": [-0.9, 2.1, 0.0]}},
    pole("pole_30", 0.9, 2.5),
    plate("limit_30", 0.56, 0.56, "speed30", [0.9, 2.2, 0.0]),
    plate("school", 0.6, 0.6, "school", [0.9, 1.55, 0.0]),
]

recipe = {
    "format": "mei-asset", "version": 1, "name": "town_road_signs",
    "budget": {"vertices": 120, "triangles": 40},
    "sheets": {"signs": {"image": SHEET}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
with open(os.path.join(HERE, "town_road_signs.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
