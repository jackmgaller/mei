#!/usr/bin/env python3
"""Writes postbox_col.asset.json: the postbox's collision, one box.

Run as `python3 carts/garden/shrinetown/assets/postbox/make_col.py`. The box is a little wider
than the pillar (0.205 radius) and stops under the cap's dome so the top is a flat floor.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def box(x0, x1, y0, y1, z0, z1):
    v = [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]
    f = [[0, 1, 2, 3], [4, 5, 6, 7], [3, 2, 5, 4], [7, 6, 1, 0], [4, 7, 0, 3], [2, 1, 6, 5]]
    return v, f


v, f = box(-0.25, 0.25, 0.0, 1.2, -0.25, 0.25)
recipe = {
    "format": "mei-asset", "version": 1, "name": "postbox_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [{"id": "body", "op": "mesh", "vertices": v, "faces": f,
               "face_materials": ["solid"] * len(f)}],
}
with open(os.path.join(HERE, "postbox_col.asset.json"), "w") as fh:
    json.dump(recipe, fh, indent=1)
    fh.write("\n")
