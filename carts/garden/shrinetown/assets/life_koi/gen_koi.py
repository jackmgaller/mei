#!/usr/bin/env python3
"""Writes art/koi_back.png and life_koi.asset.json (needs Pillow).

Shrine town's pond koi: one new fish, about 0.45 m long, placed five times by the world (each
with its own yaw and a slow swim in the cart). The body is a three-section loft with a flat
tail, a dorsal fin and two pectoral fins; its back is a 16 x 32 orange and white pattern with a
dark spot. It lies with its belly at y = 0 and swims head to -Z; the world sets the depth under
the water. 25 triangles. There is no collision: fish are not solid.
"""
import json
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

ORANGE, WHITE, DARK, DEEP = (232, 120, 42), (240, 232, 214), (44, 36, 34), (200, 80, 30)


def back():
    """16 x 32: u across the fish, v along it with the head at the top."""
    im = Image.new("RGBA", (16, 32), ORANGE + (255,))
    px = im.putpixel

    def blob(cx, cy, rx, ry, col):
        for y in range(32):
            for x in range(16):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    px((x, y), col + (255,))

    blob(8, 5, 4.5, 4, ORANGE)            # head
    blob(5, 14, 3.5, 5, WHITE)            # a white patch, then a second behind it
    blob(11, 22, 3.5, 4, WHITE)
    blob(9, 11, 2.5, 2, DEEP)
    blob(6, 24, 2, 2.5, DEEP)
    px((11, 14), DARK + (255,))
    px((12, 14), DARK + (255,))
    px((11, 15), DARK + (255,))
    im.save(os.path.join(HERE, "art", "koi_back.png"))


def tri(id_, pts):
    return {"id": id_, "op": "mesh", "material": "fin", "vertices": pts, "faces": [[0, 1, 2]]}


back()

recipe = {
    "format": "mei-asset", "version": 1, "name": "life_koi",
    "budget": {"vertices": 60, "triangles": 30},
    "materials": {
        "scales": {"color": "#e8782a",
                   "texture": {"image": "art/koi_back.png", "projection": "planar",
                               "axis": "z", "scale": [0.16, 0.44], "offset": [0.5, 0.5]}},
        "fin": {"color": "#f0a860", "palette": True, "double_sided": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "body", "op": "loft", "caps": True, "material": "scales",
         "sections": [
             {"y": -0.22, "points": [[-0.02, 0], [0, 0.02], [0.02, 0], [0, -0.02]]},
             {"y": -0.02, "points": [[-0.065, 0], [0, 0.05], [0.065, 0], [0, -0.05]]},
             {"y": 0.2, "points": [[-0.045, 0], [0, 0.04], [0.045, 0], [0, -0.04]]},
         ],
         "transform": {"rotate": [-90, 0, 0], "translate": [0, 0.05, 0]}},
        {"id": "tail", "op": "mesh", "material": "fin",
         "vertices": [[0, 0.05, 0.2], [-0.075, 0.05, 0.34], [0, 0.05, 0.29], [0.075, 0.05, 0.34]],
         "faces": [[0, 1, 2], [0, 2, 3]]},
        tri("dorsal", [[0, 0.095, 0.0], [0, 0.095, 0.12], [0, 0.16, 0.1]]),
        {"id": "pectorals", "op": "group", "children": [
            tri("pectoral", [[0.055, 0.04, -0.1], [0.14, 0.03, -0.04], [0.06, 0.04, -0.03]]),
        ], "modifiers": [{"op": "mirror", "axis": "x"}]},
    ],
}

with open(os.path.join(HERE, "life_koi.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
