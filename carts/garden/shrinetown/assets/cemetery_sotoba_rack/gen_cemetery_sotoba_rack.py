#!/usr/bin/env python3
"""Writes art/sotoba.png, cemetery_sotoba_rack.asset.json and cemetery_sotoba_rack_col.asset.json.

A wooden stand (two posts and a rail) with eight sotoba (grave tablets) leaning on it. Each
tablet is one double-sided card (2 triangles) whose cut-out head is the five-tier notched top;
the texture holds two tablets side by side, a fresh one and a weathered one. 40 triangles.
Needs Pillow.  Run: python3 gen_cemetery_sotoba_rack.py   (writes next to this script)
"""
import json, math, os, random
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

# ---- texture: 32 x 64, two tablets of 16 x 64 ----
INK = (44, 42, 40, 255)
TABLETS = [  # (body, light grain, dark grain)
    ((176, 138, 94, 255), (200, 168, 120, 255), (150, 116, 78, 255)),     # new wood
    ((138, 130, 120, 255), (162, 154, 142, 255), (112, 104, 94, 255)),    # weathered grey
]
# half-widths of the head rows from the top: five tiers, each wider, with a neck between
HEAD = [1, 2, 2, 1, 3, 3, 2, 4, 4, 3, 5, 5, 4]
img = Image.new("RGBA", (32, 64), (0, 0, 0, 0))
rng = random.Random(7)
for k, (body, lt, dk) in enumerate(TABLETS):
    x0 = 16 * k
    for y in range(64):
        hw = HEAD[y] if y < len(HEAD) else 6
        for x in range(8 - hw, 8 + hw):
            c = body
            if (x * 5 + y * 3 + k) % 11 == 0:
                c = lt
            if rng.random() < 0.06:
                c = dk
            if x == 8 - hw or x == 8 + hw - 1:
                c = dk
            img.putpixel((x0 + x, y), c)
    # ink: a tick on each tier, then a column of characters down the body
    for y in (1, 4, 7, 10):
        for x in range(7, 9):
            img.putpixel((x0 + x, y), INK)
    for y in range(17, 58):
        if y % 6 in (0, 1):
            continue
        for x in (6, 7, 8, 9):
            if (x + y * 7 + k) % 3:
                img.putpixel((x0 + x, y), INK)
img.save(os.path.join(HERE, "art", "sotoba.png"))

# ---- tablets ----
# (x, height, lean degrees, texture half 0 new / 1 weathered)
TABS = [(-0.63, 1.02, 7, 0), (-0.45, 0.95, 9, 1), (-0.27, 1.05, 6, 0), (-0.09, 0.92, 8, 1),
        (0.09, 1.04, 7, 1), (0.27, 0.96, 10, 0), (0.45, 1.03, 6, 1), (0.63, 0.94, 8, 0)]
WID = 0.16
RAIL_Y, RAIL_Z = 0.55, 0.06
RAIL_DZ = 0.05    # the rail sits behind the posts' fronts (a gap over 3 cm)
verts, uvs, faces = [], [], []
for x, h, lean, half in TABS:
    t = math.tan(math.radians(lean))
    z_rail = RAIL_Z + RAIL_DZ - 0.025 - 0.035   # 3.5 cm in front of the rail's front
    z0 = z_rail - RAIL_Y * t
    n = len(verts)
    u0, u1 = 0.5 * half + 0.02, 0.5 * half + 0.48
    for yy, v in ((0.0, 1.0), (h, 0.0)):
        for dx, u in ((-WID / 2, u0), (WID / 2, u1)):
            verts.append([round(x + dx, 4), yy, round(z0 + yy * t, 4)])
            uvs.append([u, v])
    faces += [[n, n + 2, n + 3], [n, n + 3, n + 1]]

recipe = {
    "format": "mei-asset", "version": 1, "name": "cemetery_sotoba_rack",
    "budget": {"triangles": 40},
    "materials": {
        "wood": {"color": "#5a3e2c", "palette": True},
        "tablet": {"color": "#b08a5e", "double_sided": True,
                   "texture": {"image": "art/sotoba.png", "projection": "fit"}},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "nodes": [
        {"id": "post_w", "op": "box", "size": [0.07, 0.8, 0.07], "open": ["top", "bottom"],
         "material": "wood", "transform": {"translate": [-0.76, 0.4, RAIL_Z]}},
        {"id": "post_e", "op": "box", "size": [0.07, 0.8, 0.07], "open": ["top", "bottom"],
         "material": "wood", "transform": {"translate": [0.76, 0.4, RAIL_Z]}},
        {"id": "rail", "op": "box", "size": [1.6, 0.05, 0.05], "open": ["left", "right"],
         "material": "wood", "transform": {"translate": [0, RAIL_Y, RAIL_Z + RAIL_DZ]}},
        {"id": "tablets", "op": "mesh", "vertices": verts, "uvs": uvs, "faces": faces,
         "face_materials": ["tablet"] * len(faces)},
    ],
    "lod": {"cull": 60},
    "verification": {"required": True, "depth": True, "perspective": True},
}
col = {
    "format": "mei-asset", "version": 1, "name": "cemetery_sotoba_rack_col",
    "budget": {"triangles": 10},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "nodes": [{"id": "body", "op": "box", "size": [1.6, 0.8, 0.3], "open": ["bottom"],
               "material": "solid", "transform": {"translate": [0, 0.4, 0.0]}}],
    "verification": {"required": True, "depth": True, "perspective": True},
}
for name, d in (("cemetery_sotoba_rack", recipe), ("cemetery_sotoba_rack_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
