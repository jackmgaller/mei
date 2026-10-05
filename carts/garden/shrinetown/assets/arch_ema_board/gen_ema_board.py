#!/usr/bin/env python3
"""Writes arch_ema_board.asset.json and arch_ema_board_col.asset.json.

The rack of wish plaques: two posts, a small gabled roof, two rails and house-shaped wooden
plaques hanging from them. Faces -Z; 2.0 m wide, 0.7 m deep (roof), 2.05 m tall."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))

POSTS_X = 0.8
ROWS = [(1.6, [-0.57, -0.19, 0.19, 0.57]), (1.1, [-0.5, -0.17, 0.17, 0.5])]
WOODS = ["ema_new", "ema_aged", "ema_pale"]


def plaques():
    verts, faces, mats = [], [], []
    k = 0
    for y, xs in ROWS:
        for x in xs:
            k += 1
            sw = 0.04 if k % 2 else -0.03          # tilt about the rail: the free end swings
            w, h, shoulder = 0.28, 0.32, 0.22      # apex at the rail, shoulders 0.1 below
            apex = y + 0.01
            def at(dx, yy):
                return [x + dx, yy, sw * (apex - yy) / h]
            n = len(verts)
            verts += [at(0, apex), at(w / 2, apex - 0.1), at(w / 2, apex - h),
                      at(-w / 2, apex - h), at(-w / 2, apex - 0.1)]
            faces.append([n, n + 1, n + 2, n + 3, n + 4])
            mats.append(WOODS[k % 3])
    return {"id": "plaques", "op": "mesh", "vertices": verts, "faces": faces,
            "face_materials": mats}


def roof():
    hw, ey, ridge, ez = 1.0, 1.75, 2.05, 0.35
    v = [[-hw, ey, -ez], [hw, ey, -ez], [hw, ridge, 0], [-hw, ridge, 0],
         [-hw, ey, ez], [hw, ey, ez]]
    f = [[3, 2, 1, 0],        # front slope (faces -Z and up)
         [2, 3, 4, 5],        # back slope
         [3, 0, 4],           # west gable
         [2, 5, 1],           # east gable
         [0, 1, 5, 4]]        # underside
    return {"id": "roof", "op": "mesh", "material": "tile", "vertices": v, "faces": f}


nodes = [
    {"id": "post_w", "op": "box", "size": [0.14, 2.0, 0.14], "material": "wood",
     "open": ["bottom", "top"], "transform": {"translate": [-POSTS_X, 1.0, 0]}},
    {"id": "post_e", "op": "box", "size": [0.14, 2.0, 0.14], "material": "wood",
     "open": ["bottom", "top"], "transform": {"translate": [POSTS_X, 1.0, 0]}},
    roof(),
]
for i, (y, _) in enumerate(ROWS):
    nodes.append({"id": "rail_%d" % (i + 1), "op": "box", "size": [1.7, 0.06, 0.06],
                  "material": "dark", "open": ["left", "right"],
                  "transform": {"translate": [0, y, 0]}})
nodes.append(plaques())

recipe = {
    "format": "mei-asset", "version": 1, "name": "arch_ema_board",
    "budget": {"triangles": 64},
    "materials": {
        "wood": {"color": "#8a6446", "palette": True},
        "dark": {"color": "#5a3e2c", "palette": True},
        "tile": {"color": "#3e4248", "palette": True},
        "ema_new": {"color": "#b08a5e", "palette": True, "double_sided": True},
        "ema_aged": {"color": "#8a6446", "palette": True, "double_sided": True},
        "ema_pale": {"color": "#c8a878", "palette": True, "double_sided": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
    "lod": {"cull": 60},
}
col = {
    "format": "mei-asset", "version": 1, "name": "arch_ema_board_col",
    "budget": {"triangles": 40},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "post_w", "op": "box", "size": [0.2, 1.8, 0.3], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [-POSTS_X, 0.9, 0]}},
        {"id": "post_e", "op": "box", "size": [0.2, 1.8, 0.3], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [POSTS_X, 0.9, 0]}},
        {"id": "roof", "op": "box", "size": [2.0, 0.3, 0.7], "material": "solid",
         "transform": {"translate": [0, 1.9, 0]}},
    ],
}
for name, r in (("arch_ema_board", recipe), ("arch_ema_board_col", col)):
    with open(os.path.join(here, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
