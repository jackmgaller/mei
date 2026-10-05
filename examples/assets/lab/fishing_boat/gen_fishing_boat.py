#!/usr/bin/env python3
"""Writes art/boat_sheet.png (+ .sheet.json) and fishing_boat.asset.json. Run from anywhere.

The hull is one `mesh` node: nine hollow cross-sections lofted from the transom (+Z) to the bow
(-Z), each a closed 15-point ring that runs down the outside, over the gunwale and back along
the inside, so the boat is open to the sky with a real inner wall and floor.
"""
import json, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

# ---------------------------------------------------------------- art
W, H = 64, 40
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# cell "flag" (0,0,40,24): a tairyo-bata, the flag a boat flies after a big catch
d.rectangle((0, 0, 39, 23), fill="#c8302f")
d.rectangle((0, 0, 39, 1), fill="#f2c94c")
d.rectangle((0, 22, 39, 23), fill="#f2c94c")
for x in range(0, 40, 8):                                   # little waves along the foot
    d.arc((x, 15, x + 8, 23), 180, 360, fill="#f6efe0")
    d.arc((x + 4, 17, x + 12, 25), 180, 360, fill="#e8b4a0")
d.ellipse((8, 5, 28, 15), fill="#ff9a8b")                  # a fat sea-bream
d.polygon([(27, 10), (35, 5), (35, 15)], fill="#ff9a8b")
d.polygon([(14, 5), (18, 2), (22, 5)], fill="#e4685a")
d.ellipse((11, 8, 13, 10), fill="#2a2a33")
d.line((16, 7, 16, 13), fill="#e4685a")
d.arc((8, 5, 28, 15), 100, 260, fill="#fbd0c6")

# cell "eye" (40,0,16,16): the painted eye on the bow
ox = 40
d.rectangle((ox, 0, ox + 15, 15), fill="#efe9d8")
d.ellipse((ox + 1, 2, ox + 14, 14), fill="#ffffff", outline="#2a2a33")
d.ellipse((ox + 5, 4, ox + 12, 12), fill="#1d2a3a")
d.rectangle((ox + 6, 5, ox + 7, 6), fill="#ffffff")
d.line((ox + 2, 1, ox + 10, 0), fill="#2a2a33")

im.save(os.path.join(HERE, "art", "boat_sheet.png"))
json.dump({"format": "mei-sheet", "version": 1, "cells": {
    "flag": [0, 0, 40, 24], "eye": [40, 0, 16, 16]}},
    open(os.path.join(HERE, "art", "boat_sheet.sheet.json"), "w"), indent=2)

# ---------------------------------------------------------------- hull
# per section, stern (z = +3) to bow (z = -3): half beam, gunwale height, keel height
SEC = [  # w,   top,  keel
    (0.95, 0.95, 0.14),
    (1.08, 0.88, 0.07),
    (1.14, 0.83, 0.02),
    (1.15, 0.80, 0.00),
    (1.10, 0.82, 0.01),
    (0.98, 0.90, 0.05),
    (0.76, 1.12, 0.17),
    (0.46, 1.50, 0.40),
    (0.12, 2.00, 0.80),
]
TW = 0.07
# (x as a fraction of beam, height as a fraction of depth, absolute x inset)
RING = [
    (-1.00, 1.00, 0), (-1.03, 0.80, 0), (-0.97, 0.50, 0), (-0.60, 0.12, 0), (0.0, 0.0, 0),
    (0.60, 0.12, 0), (0.97, 0.50, 0), (1.03, 0.80, 0), (1.00, 1.00, 0),
    (1.00, 1.00, -1), (0.94, 0.58, -1), (0.45, 0.26, 0),
    (-0.45, 0.26, 0), (-0.94, 0.58, 1), (-1.00, 1.00, 1),
]
EDGE_MAT = ["hull_red", "hull_white", "hull_navy", "hull_navy", "hull_navy", "hull_navy",
            "hull_white", "hull_red", "gunwale", "plank_in", "plank_in", "deck", "plank_in",
            "plank_in", "gunwale"]

verts, faces, fmats = [], [], []
rings = []
for i, (w, top, keel) in enumerate(SEC):
    z = 3.0 - 0.75 * i
    ids = []
    for fx, fy, inset in RING:
        x = fx * w + inset * min(TW, 0.3 * w)
        y = keel + fy * (top - keel)
        if (fx, fy) == (0.0, 0.0):
            x = 0.0
        ids.append(len(verts))
        verts.append([round(x, 4), round(y, 4), round(z, 4)])
    rings.append(ids)
n = len(RING)
for i in range(len(SEC) - 1):
    for j in range(n):
        a, b = rings[i][j], rings[i][(j + 1) % n]
        c, dd = rings[i + 1][(j + 1) % n], rings[i + 1][j]
        faces.append([a, b, c]); fmats.append(EDGE_MAT[j])
        faces.append([a, c, dd]); fmats.append(EDGE_MAT[j])
caps = [(rings[0], "hull_white"), (rings[-1][::-1], "hull_white")]

def volume(fs):
    v = 0.0
    for f in fs:
        p = [verts[k] for k in f]
        v += (p[0][0] * (p[1][1] * p[2][2] - p[1][2] * p[2][1])
              - p[0][1] * (p[1][0] * p[2][2] - p[1][2] * p[2][0])
              + p[0][2] * (p[1][0] * p[2][1] - p[1][1] * p[2][0])) / 6
    return v

if volume(faces) < 0:                       # make the windings outward
    faces = [f[::-1] for f in faces]
    caps = [(r[::-1], m) for r, m in caps]
# caps: choose the orientation by the cap's normal
def cap_orient(r, want_z):
    pts = [verts[k] for k in r]
    area = sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1]
               for k in range(len(pts)))
    # (x, y) counter-clockwise seen from +Z has area > 0 and normal +Z
    return r if (area > 0) == (want_z > 0) else r[::-1]
for (r, m), wz in zip(caps, (1, -1)):
    faces.append(cap_orient(r, wz)); fmats.append(m)

# ---------------------------------------------------------------- recipe
def box(i, size, mat, at, **kw):
    n = {"id": i, "op": "box", "size": size, "material": mat, "transform": {"translate": at}}
    n.update(kw)
    return n

def ball(i, r, mat, at, rings=3, seg=6, scale=None):
    t = {"translate": at}
    if scale:
        t["scale"] = scale
    return {"id": i, "op": "sphere", "radius": r, "rings": rings, "segments": seg, "material": mat, "transform": t}

materials = {
    "hull_white": {"color": "#efe9d8"},
    "hull_red": {"color": "#c8402f"},
    "hull_navy": {"color": "#27406b"},
    "gunwale": {"color": "#8a5a36"},
    "plank_in": {"color": "#d9b98a", "texture": {"pattern": "planks", "colors": ["#d9b98a", "#a9835a", "#c9a678", "#e3c79d"],
                 "params": {"boards": 4}, "projection": "box", "scale": [0.75, 0.75]}},
    "deck": {"color": "#b08a5c", "texture": {"pattern": "planks", "colors": ["#b08a5c", "#6e5030", "#9c7a50", "#c09a6a"],
             "params": {"boards": 4}, "projection": "box", "scale": [0.8, 0.8]}},
    "cabin": {"color": "#e9e3d0", "texture": {"texels": ["00000000", "01111110", "01322210", "01222210",
              "01111110", "00000000", "00000000", "00000000"],
              "colors": ["#e9e3d0", "#4a5864", "#7fbfdc", "#ffffff"], "projection": "box",
              "scale": [1.5, 1.5], "offset": [0.5, 0.5]}},
    "roof": {"color": "#c8402f"},
    "mast": {"color": "#7a5236"},
    "flag": {"color": "#c8302f", "texture": {"sheet": "sheet", "cell": "flag", "bits": 8, "projection": "fit"}},
    "eye": {"color": "#efe9d8", "texture": {"sheet": "sheet", "cell": "eye", "bits": 4, "projection": "fit"}},
    "lamp": {"color": "#ffcf6a", "class": "emissive"},
    "stack": {"color": "#3b3d46"},
    "puff": {"color": "#f3f6f8"},
    "crate": {"color": "#b98962", "texture": {"pattern": "planks", "colors": ["#b98962", "#7d5634", "#a67a52", "#c79a73"],
              "params": {"boards": 2}, "projection": "box", "scale": [0.6, 0.6]}},
    "float_a": {"color": "#f0702a"},
    "float_b": {"color": "#f6f0e0"},
    "float_c": {"color": "#4fb4a8"},
    "gull": {"color": "#f6f6f2"},
    "gull_wing": {"color": "#7e8794"},
    "beak": {"color": "#f2a93a"},
}

hull = {"id": "hull", "op": "mesh", "material": "hull_white", "vertices": verts, "faces": faces,
        "face_materials": fmats}

nodes = [
    hull,
    box("thwart_a", [1.9, 0.06, 0.28], "gunwale", [0, 0.58, -0.35]),
    box("thwart_b", [1.7, 0.06, 0.28], "gunwale", [0, 0.58, -1.45]),
    # wheelhouse
    box("cabin", [1.5, 1.5, 1.5], "cabin", [0, 1.05, 1.5], open=["bottom", "top"]),
    box("cabin_roof", [1.8, 0.08, 1.85], "roof", [0, 1.84, 1.5]),
    {"id": "stack", "op": "cylinder", "radius": 0.09, "height": 0.5, "segments": 8, "material": "stack",
     "transform": {"translate": [0.45, 2.12, 1.95]}},
    ball("puff_a", 0.1, "puff", [0.48, 2.5, 1.95]),
    ball("puff_b", 0.14, "puff", [0.55, 2.72, 1.9]),
    ball("puff_c", 0.18, "puff", [0.66, 3.0, 1.82]),
    # mast, yard and the flag
    {"id": "mast", "op": "cylinder", "radius": 0.045, "height": 1.9, "segments": 8, "caps": False,
     "material": "mast", "transform": {"translate": [0, 2.83, 0.95]}},
    box("yard", [1.5, 0.05, 0.05], "mast", [0, 3.68, 0.95]),
    box("flag", [1.3, 0.8, 0.02], "flag", [0, 3.27, 0.95]),
    ball("lantern", 0.12, "lamp", [0.0, 2.9, 0.62], rings=3, seg=8),
    box("lantern_arm", [0.04, 0.04, 0.3], "mast", [0, 3.02, 0.78]),
    # the painted eyes
    {"id": "eyes", "op": "group", "children": [
        {"id": "eye", "op": "box", "size": [0.05, 0.4, 0.4], "material": "eye",
         "transform": {"rotate": [0, -22, 0], "translate": [-0.7, 1.02, -1.7]}}],
     "modifiers": [{"op": "mirror", "axis": "x"}]},
    # cargo
    box("crate_a", [0.55, 0.34, 0.45], "crate", [-0.32, 0.4, -0.9]),
    box("crate_b", [0.55, 0.34, 0.45], "crate", [0.32, 0.4, -0.9]),
    ball("float_a", 0.15, "float_a", [0.0, 0.78, -0.88]),
    ball("float_b", 0.13, "float_b", [-0.5, 0.35, 0.45]),
    ball("float_c", 0.13, "float_c", [0.5, 0.35, 0.45]),
    # a gull on the gunwale
    {"id": "gull_body", "op": "sphere", "radius": 0.1, "rings": 3, "segments": 8, "material": "gull",
     "transform": {"scale": [1.0, 0.9, 1.7], "translate": [0.0, 1.88, -2.35]}},
    ball("gull_head", 0.07, "gull", [0.0, 2.0, -2.5], rings=2, seg=6),
    {"id": "gull_beak", "op": "cone", "radius": 0.025, "height": 0.09, "segments": 4, "material": "beak",
     "transform": {"rotate": [-90, 0, 0], "translate": [0.0, 2.0, -2.6]}},
    {"id": "gull_wings", "op": "group", "children": [
        box("wing", [0.03, 0.05, 0.24], "gull_wing", [0.1, 1.9, -2.3])],
     "modifiers": [{"op": "mirror", "axis": "x"}]},
]

recipe = {
    "format": "mei-asset", "version": 1, "name": "fishing_boat",
    "budget": {"vertices": 900, "triangles": 1000},
    "sheets": {"sheet": {"image": "art/boat_sheet.png"}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
json.dump(recipe, open(os.path.join(HERE, "fishing_boat.asset.json"), "w"), indent=1)
