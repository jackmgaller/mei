#!/usr/bin/env python3
"""Writes forest_root_curtain and its collision.  Run: python3 gen.py

The curtain fills the sacred cedar's root door (1.4 x 2.3 m): roots hanging from a lintel root,
a cutout sheet of finer strands over a gold glow.  Origin: centre of the door's foot; the front
(the side seen from the basin) faces -Z, the cedar's trunk is at +Z."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
POL = {"required": True, "depth": True, "perspective": True}
LIGHT = {"mode": "vertical", "ambient": 0.5}


def strands():
    """32 x 56 texel grid, 0 = hole.  Hanging wavy strands of two barks, tips ragged."""
    w, h = 32, 56
    g = [[0] * w for _ in range(h)]
    # (centre column, width, drift period, drift size, length in rows, colour)
    for c, wd, per, amp, ln, col in [(3, 2, 14, 1, 52, 1), (8, 3, 18, 2, 44, 2), (13, 2, 11, 1, 56, 1),
                                     (18, 2, 16, 2, 38, 2), (23, 3, 13, 1, 50, 1), (28, 2, 17, 2, 46, 2),
                                     (6, 1, 9, 1, 24, 2), (21, 1, 10, 1, 30, 1), (30, 1, 8, 1, 20, 2)]:
        for y in range(min(ln, h)):
            drift = int(round(amp * ((y % per) / per * 2 - 1) * (1 if (y // per) % 2 == 0 else -1)))
            x0 = c + drift
            ww = wd if y < ln - 8 else max(1, wd - 1)
            for k in range(ww):
                if 0 <= x0 + k < w:
                    g[y][x0 + k] = col
    # a few cross-roots joining strands near the top
    for y, x0, x1 in [(6, 3, 14), (9, 15, 29), (14, 8, 20)]:
        for x in range(x0, x1):
            g[y][x] = 1
    return ["".join("%x" % v for v in row) for row in g]


MATS = {
    "bark": {"color": "#4a3a2e",
             "texture": {"pattern": "grain", "size": 16, "colors": ["#4a3a2e", "#35291f", "#6a4632"],
                         "params": {"rings": 3, "waves": 1, "amplitude": 2},
                         "projection": "cylindrical", "scale": [0.6, 0.6]}},
    "strands": {"color": "#4a3a2e",
                "texture": {"texels": strands(), "clear": "#000000",
                            "colors": ["#000000", "#4a3a2e", "#6a4632"], "projection": "fit"}},
    "glow": {"color": "#f0c850", "class": "emissive",
             "texture": {"texels": ["22222222", "21111112", "21000012", "21000012", "21000012",
                                    "21000012", "21000012", "21000012", "21111112", "22222222"],
                         "colors": ["#fff0b0", "#f6d870", "#d8a838"], "projection": "fit"}},
}


def cone(nid, r, h, x, top, z, seg, mat="bark", caps=False, rotate=None):
    """A root hanging from y = top: tip down."""
    return {"id": nid, "op": "cone", "radius": r, "height": h, "segments": seg, "caps": caps,
            "material": mat, "transform": {"rotate": rotate or [180, 0, 0], "translate": [x, top - h / 2, z]}}


nodes = [
    {"id": "glow", "op": "box", "size": [1.4, 2.3, 0.04], "material": "glow",
     "open": ["left", "right", "top", "bottom", "front"], "transform": {"translate": [0, 1.15, 0.25]}},
    {"id": "strands", "op": "box", "size": [1.6, 2.5, 0.04], "material": "strands",
     "open": ["left", "right", "top", "bottom", "front"],
     "transform": {"translate": [0, 1.25, 0.06]}},
    {"id": "lintel", "op": "cone", "radius": 0.17, "height": 1.9, "segments": 5, "caps": False,
     "material": "bark", "transform": {"rotate": [0, 0, 90], "translate": [-0.05, 2.3, -0.04]}},
    {"id": "sill", "op": "cone", "radius": 0.14, "height": 1.7, "segments": 5, "caps": False,
     "material": "bark", "transform": {"rotate": [0, 0, -90], "translate": [0.05, 0.15, -0.08]}},
    cone("jamb_w", 0.13, 2.4, -0.76, 2.4, -0.02, 3),
    cone("jamb_e", 0.12, 2.3, 0.76, 2.35, -0.02, 3),
    cone("root_0", 0.09, 2.15, -0.5, 2.3, -0.10, 4),
    cone("root_1", 0.08, 2.25, -0.18, 2.3, -0.06, 4),
    cone("root_2", 0.10, 1.8, 0.12, 2.3, -0.12, 4),
    cone("root_3", 0.08, 2.1, 0.40, 2.3, -0.07, 4),
    cone("root_4", 0.07, 1.6, 0.60, 2.3, -0.10, 4),
    cone("rootlet_0", 0.045, 1.1, -0.34, 2.3, -0.14, 4),
    cone("rootlet_1", 0.045, 1.0, 0.27, 2.3, -0.15, 4),
    cone("rootlet_2", 0.045, 0.8, -0.64, 2.3, -0.13, 4),
]

recipe = {"format": "mei-asset", "version": 1, "name": "forest_root_curtain",
          "budget": {"triangles": 60}, "materials": MATS, "lighting": LIGHT,
          "verification": POL, "nodes": nodes}
col = {"format": "mei-asset", "version": 1, "name": "forest_root_curtain_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}}, "lighting": LIGHT,
       "verification": POL,
       "nodes": [{"id": "plug", "op": "box", "size": [1.5, 2.4, 0.3], "material": "solid",
                  "transform": {"translate": [0, 1.2, 0.1]}}]}
for name, r in (("forest_root_curtain", recipe), ("forest_root_curtain_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
