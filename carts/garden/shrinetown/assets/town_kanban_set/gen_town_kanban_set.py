#!/usr/bin/env python3
"""Writes town_kanban_set.asset.json: three shop signs side by side, about 2.8 m wide.

Run from anywhere. The art is the sign sheet, ../town_signs_sheet/town_signs.png (drawn by
../town_signs_sheet/draw_signs.py). Origin: the middle of the row at its foot, the signs face -Z.
West to east: a chalk A-frame menu board (tatekanban), a lit 喫茶 pole sign, and a 手打そば board
hanging from a bracket post (tsuridashi kanban).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = "../town_signs_sheet/town_signs.png"


def tex(cell, **kw):
    m = {"color": "#f4f1e6", "texture": {"sheet": "signs", "cell": cell, "projection": "fit"}}
    m.update(kw)
    return m


materials = {
    "aframe": tex("aframe"),
    "cafe": tex("cafe", **{"class": "emissive"}),
    "soba": tex("soba"),
    "steel": {"color": "#a8a69e", "palette": True},
    "wood": {"color": "#5a3e2c", "palette": True},
    "lacquer": {"color": "#a8321e", "palette": True},
}

SIDES = ["left", "right", "top", "bottom"]

# A-frame: two boards leaning together, meeting at the top; hollow between them.
TILT, BW, BH = 12.0, 0.7, 0.98
lean = math.sin(math.radians(TILT)) * BH / 2
foot = lean                        # the tops meet at z = 0
cy = BH / 2 * math.cos(math.radians(TILT)) + 0.005
nodes = [
    {"id": "aframe_front", "op": "box", "size": [BW, BH, 0.03], "material": "wood", "open": SIDES,
     "faces": {"back": "aframe"},
     "transform": {"rotate": [TILT, 0, 0], "translate": [-0.95, cy, -foot]}},
    {"id": "aframe_back", "op": "box", "size": [BW, BH, 0.03], "material": "wood", "open": SIDES,
     "faces": {"front": "aframe"},
     "transform": {"rotate": [-TILT, 0, 0], "translate": [-0.95, cy, foot]}},
    # Pole sign: a lit box on a steel post.
    {"id": "cafe_post", "op": "box", "size": [0.07, 1.7, 0.07], "material": "steel",
     "open": ["top", "bottom"], "transform": {"translate": [0.0, 0.84, 0.0]}},
    {"id": "cafe_box", "op": "box", "size": [0.4, 0.9, 0.14], "material": "lacquer",
     "faces": {"back": "cafe", "front": "cafe"}, "transform": {"translate": [0.0, 1.95, 0.0]}},
    # Bracket post with a hanging board.
    {"id": "bracket_post", "op": "box", "size": [0.1, 2.35, 0.14], "material": "wood",
     "open": ["top", "bottom"], "transform": {"translate": [0.75, 1.165, 0.0]}},
    {"id": "bracket_arm", "op": "box", "size": [0.95, 0.06, 0.06], "material": "wood",
     "transform": {"translate": [1.225, 2.2, 0.0]}},
    {"id": "soba_board", "op": "box", "size": [0.84, 0.24, 0.05], "material": "wood",
     "faces": {"back": "soba", "front": "soba"}, "transform": {"translate": [1.25, 2.07, -0.052]}},
]

recipe = {
    "format": "mei-asset", "version": 1, "name": "town_kanban_set",
    "budget": {"vertices": 160, "triangles": 60},
    "sheets": {"signs": {"image": SHEET}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
with open(os.path.join(HERE, "town_kanban_set.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
