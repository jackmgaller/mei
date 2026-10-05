#!/usr/bin/env python3
"""Writes town_taxi_rank.asset.json: the station plaza's taxi stand, 3.2 x 1.0 m.

Run from anywhere. The art is the sign sheet, ../town_signs_sheet/town_signs.png (drawn by
../town_signs_sheet/draw_signs.py). Origin: the middle of the island at its foot, the sign faces
-Z. A low kerbed island (yellow kerb), a lit タクシーのりば sign on a post, a pipe rail for the queue.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = "../town_signs_sheet/town_signs.png"

materials = {
    "taxi": {"color": "#f4f1e6", "class": "emissive",
             "texture": {"sheet": "signs", "cell": "taxi", "projection": "fit"}},
    "paving": {"color": "#c8c4b8", "palette": True},
    "kerb": {"color": "#a8a69e", "palette": True},
    "paint": {"color": "#d8b048", "palette": True},       # yellow kerb paint
    "steel": {"color": "#8e887c", "palette": True},
    "rail": {"color": "#3a6ab0", "palette": True},
    "frame": {"color": "#2c2a28", "palette": True},
}

TOP = 0.14     # the island's top
nodes = [
    {"id": "island", "op": "box", "size": [3.2, TOP, 1.0], "material": "kerb", "open": ["bottom"],
     "faces": {"top": "paving", "back": "paint"}, "transform": {"translate": [0.0, TOP / 2, 0.0]}},
    # The sign: a lit box on a post, both faces lettered.
    {"id": "sign_post", "op": "box", "size": [0.09, 2.4, 0.09], "material": "steel",
     "open": ["top", "bottom"], "transform": {"translate": [-1.3, TOP + 1.2 - 0.01, 0.0]}},
    {"id": "sign", "op": "box", "size": [0.96, 0.48, 0.14], "material": "frame",
     "faces": {"back": "taxi", "front": "taxi"}, "transform": {"translate": [-1.3, TOP + 2.17, 0.0]}},
    # The queue rail: two stanchions and a bar behind them.
    {"id": "stanchion_w", "op": "box", "size": [0.06, 0.9, 0.08], "material": "rail",
     "open": ["top", "bottom"], "transform": {"translate": [-0.5, TOP + 0.44, -0.2]}},
    {"id": "stanchion_e", "op": "box", "size": [0.06, 0.9, 0.08], "material": "rail",
     "open": ["top", "bottom"], "transform": {"translate": [1.3, TOP + 0.44, -0.2]}},
    {"id": "rail_bar", "op": "box", "size": [1.8, 0.05, 0.06], "material": "rail", "open": ["left", "right"],
     "transform": {"translate": [0.4, TOP + 0.76, -0.15]}},
]

recipe = {
    "format": "mei-asset", "version": 1, "name": "town_taxi_rank",
    "budget": {"vertices": 160, "triangles": 60},
    "sheets": {"signs": {"image": SHEET}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
with open(os.path.join(HERE, "town_taxi_rank.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
