#!/usr/bin/env python3
"""Writes arch_omikuji_rack.asset.json and arch_omikuji_rack_col.asset.json.

The rack where fortune slips are tied: two posts, a roofed top beam and two rope rails, with
paper slips hanging from the rails. Faces -Z; 1.9 m wide, 0.3 m deep, 1.9 m tall."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))

POSTS_X = 0.8
BARS = [(1.45, [-0.55, -0.19, 0.19, 0.55]), (1.0, [-0.5, -0.17, 0.17, 0.5])]


def slips():
    verts, faces, mats = [], [], []
    k = 0
    for y, xs in BARS:
        for x in xs:
            k += 1
            sw = 0.03 if k % 2 else -0.03          # swing of the free end, toward / away
            w, h = 0.1, 0.34
            top, bot = y + 0.01, y + 0.01 - h
            n = len(verts)
            verts += [[x - w / 2, top, 0], [x + w / 2, top, 0],
                      [x + w / 2, bot, sw - 0.0], [x - w / 2, bot, sw]]
            faces.append([n, n + 1, n + 2, n + 3])
            mats.append("paper" if k % 3 else "paper_old")
    return {"id": "slips", "op": "mesh", "vertices": verts, "faces": faces,
            "face_materials": mats}


nodes = [
    {"id": "post_w", "op": "box", "size": [0.12, 1.82, 0.12], "material": "wood",
     "open": ["bottom", "top"], "transform": {"translate": [-POSTS_X, 0.91, 0]}},
    {"id": "post_e", "op": "box", "size": [0.12, 1.82, 0.12], "material": "wood",
     "open": ["bottom", "top"], "transform": {"translate": [POSTS_X, 0.91, 0]}},
    {"id": "beam", "op": "box", "size": [1.9, 0.1, 0.3], "material": "dark",
     "transform": {"translate": [0, 1.85, 0]}},
]
for i, (y, _) in enumerate(BARS):
    nodes.append({"id": "rail_%d" % (i + 1), "op": "box", "size": [1.7, 0.05, 0.05],
                  "material": "dark", "open": ["left", "right"],
                  "transform": {"translate": [0, y, 0]}})
nodes.append(slips())

recipe = {
    "format": "mei-asset", "version": 1, "name": "arch_omikuji_rack",
    "budget": {"triangles": 64},
    "materials": {
        "wood": {"color": "#8a6446", "palette": True},
        "dark": {"color": "#5a3e2c", "palette": True},
        "paper": {"color": "#ece4d2", "palette": True, "double_sided": True},
        "paper_old": {"color": "#d4c8a8", "palette": True, "double_sided": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
    "lod": {"cull": 60},
}
col = {
    "format": "mei-asset", "version": 1, "name": "arch_omikuji_rack_col",
    "budget": {"triangles": 40},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "post_w", "op": "box", "size": [0.2, 1.8, 0.3], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [-POSTS_X, 0.9, 0]}},
        {"id": "post_e", "op": "box", "size": [0.2, 1.8, 0.3], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [POSTS_X, 0.9, 0]}},
        {"id": "beam", "op": "box", "size": [1.9, 0.2, 0.4], "material": "solid",
         "transform": {"translate": [0, 1.85, 0]}},
    ],
}
for name, r in (("arch_omikuji_rack", recipe), ("arch_omikuji_rack_col", col)):
    with open(os.path.join(here, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
