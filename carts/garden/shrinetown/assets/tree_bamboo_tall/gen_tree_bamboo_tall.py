#!/usr/bin/env python3
"""Writes tree_bamboo_tall.asset.json and tree_bamboo_tall_col.asset.json.

A 12 m bamboo culm in three crossing cards (12 triangles), with the foliage sheet's `bamboo`
cell split into a plain-culm lower part and a leafy crown, so the leaves stay near the top.
Run: python3 gen_tree_bamboo_tall.py   (writes next to this script)
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
H = 12.0
SPLIT_Y = 8.0     # height where the crown part of each card begins
SPLIT_V = 0.58    # v of the bamboo cell where its leaves begin (culms only below)

# (yaw degrees, half width, lean x, lean z at the top, base offset x, z)
CARDS = [
    (0, 1.15, 0.30, 0.10, 0.0, 0.0),
    (62, 1.00, -0.25, 0.30, 0.05, -0.04),
    (121, 0.90, 0.10, -0.35, -0.04, 0.05),
]


def card(yaw, hw, lx, lz, ox, oz):
    a = math.radians(yaw)
    dx, dz = math.cos(a), math.sin(a)
    verts, uvs = [], []
    for y, v in [(0.0, 1.0), (SPLIT_Y, SPLIT_V), (H, 0.0)]:
        t = y / H
        cx, cz = ox + lx * t * t, oz + lz * t * t
        verts.append([round(cx - dx * hw, 4), y, round(cz - dz * hw, 4)])
        verts.append([round(cx + dx * hw, 4), y, round(cz + dz * hw, 4)])
        uvs += [[0.0, v], [1.0, v]]
    faces = [[0, 1, 3], [0, 3, 2], [2, 3, 5], [2, 5, 4]]
    return verts, uvs, faces


def culms(cards):
    verts, uvs, faces = [], [], []
    for c in cards:
        v, u, f = card(*c)
        n = len(verts)
        verts += v
        uvs += u
        faces += [[i + n for i in t] for t in f]
    return {"id": "culms", "op": "mesh", "vertices": verts, "faces": faces,
            "face_materials": ["bamboo"] * len(faces), "uvs": uvs}


def far_card(yaw, hw, lx, lz, ox, oz):
    """One whole-texture card (2 triangles) for the far level."""
    a = math.radians(yaw)
    dx, dz = math.cos(a), math.sin(a)
    tx, tz = ox + lx, oz + lz
    verts = [[ox - dx * hw, 0.0, oz - dz * hw], [ox + dx * hw, 0.0, oz + dz * hw],
             [tx + dx * hw, H, tz + dz * hw], [tx - dx * hw, H, tz - dz * hw]]
    return {"id": "culms", "op": "mesh", "vertices": [[round(c, 4) for c in v] for v in verts],
            "faces": [[0, 1, 2], [0, 2, 3]], "face_materials": ["bamboo"] * 2,
            "uvs": [[0, 1], [1, 1], [1, 0], [0, 0]]}


recipe = {
    "format": "mei-asset", "version": 1, "name": "tree_bamboo_tall",
    "budget": {"triangles": 12},
    "sheets": {"foliage": {"image": "../../../shrine/assets/art/foliage.png"}},
    "materials": {"bamboo": {"color": "#a8b860", "double_sided": True,
                             "texture": {"sheet": "foliage", "cell": "bamboo", "projection": "fit"}}},
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "nodes": [culms(CARDS)],
    "lod": {"levels": [
        {"distance": 35, "nodes": [culms(CARDS[:2])]},
        {"distance": 70, "nodes": [far_card(*CARDS[0])]},
    ], "cull": 120},
    "verification": {"required": True, "depth": True, "perspective": True},
}
col = {
    "format": "mei-asset", "version": 1, "name": "tree_bamboo_tall_col",
    "budget": {"triangles": 8},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "nodes": [{"id": "stalk", "op": "box", "size": [0.24, H, 0.24], "open": ["top", "bottom"],
               "material": "solid", "transform": {"translate": [0.0, H / 2, 0.0]}}],
    "verification": {"required": True, "depth": True, "perspective": True},
}
for name, d in (("tree_bamboo_tall", recipe), ("tree_bamboo_tall_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
