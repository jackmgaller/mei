#!/usr/bin/env python3
"""Writes forest_shide_rope.asset.json: the cedar rope with its paper streamers (shide).

The rope runs along Z, 24 m on the plan, from the rope deck (z = -12, high end) to the knot hole
(z = +12), falling 2.5 m. Its centre line is 1.4 m above the origin at z = +12 and 3.9 m at
z = -12, so the streamers hang clear of y = 0. Eight zigzag streamers, each three folded panels
(6 triangles), alternately turned so they show from the deck, from the tree and from the side.
Run: python3 gen_forest_shide_rope.py   (writes next to this script)
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
SPAN, DROP = 24.0, 2.5
LOW_Y = 1.4                       # rope centre at its low end (z = +12)
THICK = 0.2

# (z along the rope, yaw degrees, length) -- uneven on purpose
STREAMERS = [(-10.3, 42, 1.3), (-7.6, -48, 1.1), (-4.9, 45, 1.4), (-2.0, -40, 1.2),
             (0.9, 50, 1.3), (3.8, -45, 1.1), (6.9, 38, 1.4), (9.6, -50, 1.2)]
XS = [0.0, 0.22, -0.2]           # the ribbon's centre at each fold level (a fourth is 0.0)
W = 0.34                          # ribbon width


def rope_y(z):
    return LOW_Y + (SPAN / 2 - z) * DROP / SPAN


def streamer(z, yaw, length, flat=False):
    a = math.radians(yaw)
    ca, sa = math.cos(a), math.sin(a)
    n = 3
    xs = [0.0, 0.0] if flat else (XS + [0.0])[:n + 1]
    verts, faces, mats = [], [], []
    top = rope_y(z) - 0.04
    for j in range(len(xs)):
        y = top - length * j / (len(xs) - 1)
        for dx in (-W / 2, W / 2):
            x = xs[j] + dx
            verts.append([round(x * ca, 4), round(y, 4), round(z - x * sa, 4)])
    for j in range(len(xs) - 1):
        o = 2 * j
        # corners clockwise as seen from -Z: top-left, top-right, bottom-right, bottom-left
        # two triangles per panel: rounded corners are not exactly planar
        faces += [[o, o + 1, o + 3], [o, o + 3, o + 2]]
        mats += 2 * ["paper" if j % 2 == 0 else "paper_shade"]
    return verts, faces, mats


def streamers(flat=False):
    verts, faces, mats = [], [], []
    for z, yaw, length in STREAMERS:
        v, f, m = streamer(z, yaw, length, flat)
        n = len(verts)
        verts += v
        faces += [[i + n for i in q] for q in f]
        mats += m
    return {"id": "streamers", "op": "mesh", "vertices": verts, "faces": faces, "face_materials": mats}


length = math.hypot(SPAN, DROP)
rope = {"id": "rope", "op": "box", "size": [THICK, THICK, length], "open": ["back", "front"],
        "material": "straw",
        "transform": {"rotate": [round(math.degrees(math.atan2(DROP, SPAN)), 3), 0, 0],
                      "translate": [0, round(LOW_Y + DROP / 2, 3), 0]}}
recipe = {
    "format": "mei-asset", "version": 1, "name": "forest_shide_rope",
    "budget": {"triangles": 60},
    "materials": {
        "straw": {"color": "#b8a068", "palette": True},
        "paper": {"color": "#ece4d2", "palette": True, "double_sided": True},
        "paper_shade": {"color": "#cfc6b0", "palette": True, "double_sided": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "nodes": [rope, streamers()],
    "lod": {"levels": [{"distance": 45, "nodes": [rope, streamers(flat=True)]}]},
    "verification": {"required": True, "depth": True, "perspective": True},
}
with open(os.path.join(HERE, "forest_shide_rope.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
