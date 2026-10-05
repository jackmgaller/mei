#!/usr/bin/env python3
"""Writes forest_stage_bell and its collision.  Run: python3 gen.py

A temple bell (bonsho) hung from a beam under the stage hall's eaves, with its striking log
(shumoku) on two ropes and the pull rope (star 3's touch switch) tied to the log's front end.
Origin: on the deck under the bell, centre of the footprint; the front (the side the player
comes from) faces -Z; the hall is behind, at +Z.  The beam's top is at y = 3.55, where the
eaves' underside should be.  The pull rope is the touch target: x 0, z -1.85, y 0.55 to 1.5."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
POL = {"required": True, "depth": True, "perspective": True}
LIGHT = {"mode": "vertical", "ambient": 0.5}

MATS = {
    "bronze": {"color": "#5f7a4a", "double_sided": True,
               "texture": {"pattern": "grain", "size": 16, "colors": ["#6a7a50", "#4e6644", "#8a8a5a"],
                           "params": {"rings": 2, "waves": 1, "amplitude": 1},
                           "projection": "cylindrical", "scale": [1.7, 1.0]}},
    "bell_in": {"color": "#2c2a28", "palette": True},
    "wood": {"color": "#8a6446",
             "texture": {"pattern": "grain", "size": 16, "colors": ["#8a6446", "#6a4a36", "#a07c58"],
                         "params": {"rings": 3, "waves": 1, "amplitude": 2},
                         "projection": "box", "scale": [1.0, 0.5]}},
    "rope": {"color": "#c8b890",
             "texture": {"pattern": "stripes", "size": 8, "colors": ["#c8b890", "#8a7a56"],
                         "params": {"count": 4, "axis": "v"}, "projection": "box", "scale": [0.25, 0.25]}},
}

# bonsho profile [radius, y]: lip at y 1.0 up to the crown at 2.85
bell_profile = [[0.64, 1.2], [0.6, 1.55], [0.5, 2.2], [0.3, 2.65], [0.12, 2.9]]

BEAM_TOP = 3.55


def rope(nid, x, z, y0, y1, w=0.07):
    return {"id": nid, "op": "box", "size": [w, y1 - y0, w], "material": "rope", "open": ["top", "bottom"],
            "transform": {"translate": [x, (y0 + y1) / 2, z]}}


def nodes(segs=6, detail=True):
    n = [
        {"id": "bell", "op": "lathe", "profile": bell_profile, "segments": segs, "caps": False,
         "material": "bronze"},
        {"id": "beam", "op": "box", "size": [2.4, 0.3, 0.3], "material": "wood", 
         "transform": {"translate": [0, BEAM_TOP - 0.15, 0.1]}},
        {"id": "arm", "op": "box", "size": [0.26, 0.22, 2.3], "material": "wood", "open": ["front"],
         "transform": {"translate": [0, BEAM_TOP - 0.15, -0.95]}},
    ]
    if detail:
        n += [
            {"id": "hanger", "op": "box", "size": [0.12, 0.6, 0.18], "material": "bell_in", "open": ["top", "bottom"],
             "transform": {"translate": [0, 3.1, 0.0]}},
            {"id": "log", "op": "cylinder", "radius": 0.13, "height": 1.5, "segments": 4, "material": "wood",
             "transform": {"rotate": [90, 0, 0], "translate": [0, 1.65, -1.2]}},
            rope("log_rope_0", 0, -0.75, 1.75, BEAM_TOP - 0.28, 0.05),
            rope("log_rope_1", 0, -1.6, 1.75, BEAM_TOP - 0.28, 0.05),
            rope("pull_rope", 0, -1.85, 0.55, 1.6, 0.1),
        ]
    return n


recipe = {"format": "mei-asset", "version": 1, "name": "forest_stage_bell",
          "budget": {"triangles": 120}, "materials": MATS, "lighting": LIGHT, "verification": POL,
          "nodes": nodes(),
          "lod": {"levels": [{"distance": 30, "nodes": [
              {"id": "bell", "op": "lathe", "profile": bell_profile, "segments": 5, "caps": False,
               "material": "bronze"},
              {"id": "beam", "op": "box", "size": [2.4, 0.3, 0.3], "material": "wood",
               "open": ["left", "right", "back", "top", "bottom"],
               "transform": {"translate": [0, BEAM_TOP - 0.15, 0.1]}},
              rope("pull_rope", 0, -1.85, 0.55, 1.6, 0.1)]}], "cull": 80}}
col = {"format": "mei-asset", "version": 1, "name": "forest_stage_bell_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}}, "lighting": LIGHT,
       "verification": POL,
       "nodes": [{"id": "bell", "op": "box", "size": [1.0, 1.9, 1.0], "material": "solid",
                  "transform": {"translate": [0, 1.95, 0]}},
                 {"id": "log", "op": "box", "size": [0.3, 0.3, 1.5], "material": "solid",
                  "transform": {"translate": [0, 1.65, -1.2]}}]}
for name, r in (("forest_stage_bell", recipe), ("forest_stage_bell_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
