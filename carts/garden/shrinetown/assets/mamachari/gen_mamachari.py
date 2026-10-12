#!/usr/bin/env python3
"""Writes mamachari.asset.json and mamachari_col.asset.json next to this script.

Shrine town's everyday bicycle: the lab's mamachari cut to 120 triangles. Wheels are a flat
spoked disc inside a thin tyre ring, the frame is six three-sided tubes, and the basket, the
chain case and the green leek keep the lab bike's charm. Front is -Z.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def r4(v):
    return round(v, 4)


def tube(id_, a, b, radius, material, segments=3, caps=False, op="cylinder"):
    """A cylinder (or cone) between points a and b (rotate X then Y turns +Y onto the direction)."""
    d = [b[i] - a[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in d))
    d = [c / n for c in d]
    rx = math.degrees(math.acos(max(-1, min(1, d[1]))))
    ry = math.degrees(math.atan2(d[0], d[2]))
    mid = [(a[i] + b[i]) / 2 for i in range(3)]
    return {"id": id_, "op": op, "radius": radius, "height": r4(n), "segments": segments,
            "caps": caps, "material": material,
            "transform": {"rotate": [r4(rx), r4(ry), 0], "translate": [r4(c) for c in mid]}}


def quad_strip(id_, pts, width, material):
    """A strip of quads along (y, z) points, width in x."""
    v, f = [], []
    for y, z in pts:
        v += [[-width / 2, y, z], [width / 2, y, z]]
    for i in range(len(pts) - 1):
        k = 2 * i
        f.append([k, k + 1, k + 3, k + 2])
    return {"id": id_, "op": "mesh", "material": material, "vertices": v, "faces": f}


R = 0.33
F = (0, R, -0.56)   # front hub
RH = (0, R, 0.54)   # rear hub
BB = (0, 0.27, 0.04)
HEAD = (0, 1.0, -0.24)
SEAT = (0, 0.9, 0.22)

N = 8
rim = [[0, r4(R * math.cos(2 * math.pi * (i + 0.5) / N)), r4(R * math.sin(2 * math.pi * (i + 0.5) / N))]
       for i in range(N)]

recipe = {
    "format": "mei-asset", "version": 1, "name": "mamachari",
    "budget": {"vertices": 160, "triangles": 120},
    "sheets": {"bike": {"image": "art/bike_sheet.png"}},
    "materials": {
        "frame": {"color": "#7fcab6", "palette": True},
        "chrome": {"color": "#c9ced6", "palette": True, "double_sided": True},
        "tyre": {"color": "#2b2a30", "palette": True, "double_sided": True},
        "saddle": {"color": "#4a3426", "palette": True},
        "leek_white": {"color": "#eef0dc", "palette": True},
        "leek_green": {"color": "#4f9a3c", "palette": True},
        "wheel": {"color": "#b8bec8", "double_sided": True,
                  "texture": {"sheet": "bike", "cell": "wheel", "projection": "disc", "axis": "x",
                              "scale": [0.66, 0.66]}},
        "case": {"color": "#f1e8d2", "double_sided": True,
                 "texture": {"sheet": "bike", "cell": "case", "projection": "fit"}},
        "basket": {"color": "#cfd3da", "double_sided": True,
                   "texture": {"texels": ["1111111111111"] + ["1000100010001"] * 3 + ["1111111111111"]
                               + ["1000100010001"] * 3 + ["1111111111111"] + ["1000100010001"] * 3
                               + ["1111111111111"],
                               "colors": ["#000000", "#cfd3da"], "clear": "#000000",
                               "projection": "fit"}},
        "carrier": {"color": "#c0c5ce", "double_sided": True,
                    "texture": {"texels": ["1111111"] + ["1001001"] * 4 + ["1111111"] + ["1001001"] * 4
                                + ["1111111"] + ["1001001"] * 4 + ["1111111"],
                                "colors": ["#000000", "#c0c5ce"], "clear": "#000000",
                                "projection": "fit"}},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "prototypes": {"wheel": {"id": "wheel", "op": "group", "children": [
        {"id": "tyre", "op": "cylinder", "radius": R, "height": 0.045, "segments": N, "caps": False,
         "material": "tyre", "transform": {"rotate": [0, 0, 90]}},
        {"id": "spokes", "op": "mesh", "material": "wheel", "vertices": rim,
         "faces": [list(range(N))]}]}},
    "nodes": [
        {"id": "front_wheel", "op": "instance", "ref": "wheel", "transform": {"translate": list(F)}},
        {"id": "rear_wheel", "op": "instance", "ref": "wheel", "transform": {"translate": list(RH)}},
        tube("fork", F, HEAD, 0.016, "chrome"),
        tube("bar", (-0.28, 1.0, -0.24), (0.28, 1.0, -0.24), 0.016, "chrome"),
        tube("down_tube", (0, 0.75, -0.29), (0, 0.25, 0.01), 0.032, "frame"),
        tube("seat_tube", (0, 0.29, 0.05), SEAT, 0.026, "frame"),
        tube("chainstay", (0.03, 0.27, 0.04), (0.03, R, 0.54), 0.016, "frame"),
        tube("seatstay", (-0.05, 0.86, 0.21), (-0.05, R, 0.54), 0.016, "frame"),
        {"id": "saddle", "op": "cylinder", "radius": 0.075, "height": 0.26, "segments": 3, "caps": False,
         "material": "saddle", "transform": {"rotate": [90, 0, 0], "scale": [1.1, 1, 0.55],
                                              "translate": [0, 0.97, 0.27]}},
        {"id": "basket", "op": "box", "size": [0.38, 0.24, 0.3], "open": ["top"], "material": "basket",
         "transform": {"translate": [0, 0.86, -0.67]}},
        {"id": "carrier", "op": "mesh", "material": "carrier",
         "vertices": [[-0.105, 0.735, 0.8], [0.105, 0.735, 0.8], [0.105, 0.735, 0.26],
                      [-0.105, 0.735, 0.26]], "faces": [[0, 1, 2, 3]]},
        quad_strip("front_fender", [(0.455, -0.9), (0.668, -0.697), (0.565, -0.28)], 0.075, "chrome"),
        quad_strip("rear_fender", [(0.565, 0.26), (0.693, 0.5), (0.381, 0.9)], 0.075, "chrome"),
        {"id": "chain_case", "op": "mesh", "material": "case",
         "vertices": [[0.085, 0.28, -0.075], [0.085, 0.385, -0.02], [0.085, 0.39, 0.55],
                      [0.085, 0.30, 0.6], [0.085, 0.2, 0.55], [0.085, 0.155, -0.02]],
         "faces": [[0, 1, 2, 3, 4, 5]]},
        tube("leek_white", (-0.1, 0.9, -0.64), (-0.15, 1.12, -0.58), 0.02, "leek_white"),
        tube("leek_green", (-0.15, 1.12, -0.58), (-0.2, 1.34, -0.5), 0.03, "leek_green", op="cone"),
    ],
}
recipe["prototypes"]["wheel_lo"] = {"id": "wheel_lo", "op": "mesh", "material": "wheel", "vertices": rim,
                                    "faces": [list(range(N))]}
recipe["lod"] = {"levels": [{"distance": 18, "nodes": [
    {"id": "front_wheel", "op": "instance", "ref": "wheel_lo", "transform": {"translate": list(F)}},
    {"id": "rear_wheel", "op": "instance", "ref": "wheel_lo", "transform": {"translate": list(RH)}},
    tube("frame", (0, 0.78, -0.33), RH, 0.03, "frame"),
    {"id": "basket", "op": "box", "size": [0.38, 0.24, 0.3], "open": ["top", "bottom"],
     "material": "basket", "transform": {"translate": [0, 0.86, -0.67]}}]}],
    "cull": 40}

col = {
    "format": "mei-asset", "version": 1, "name": "mamachari_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [{"id": "body", "op": "box", "size": [0.3, 0.8, 1.7], "material": "solid",
               "open": ["bottom"], "transform": {"translate": [0, 0.4, -0.06]}}],
}

for name, data in (("mamachari", recipe), ("mamachari_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
