#!/usr/bin/env python3
"""Writes art/wheel_sheet.png (+ .sheet.json) and ferris_wheel.asset.json. Run from anywhere.

The wheel stands in the XY plane facing -Z. Its two candy-striped rims are one `mesh` node;
the sixteen gondolas are instances of four prototypes, hung upright at the rim's corners.
"""
import json, math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

# ---------------------------------------------------------------- art
im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 31, 31), fill="#e8791f")                 # the hub's side smears this colour
d.ellipse((1, 1, 30, 30), fill="#f4a02a", outline="#e8791f")
d.ellipse((4, 4, 27, 27), fill="#ffd84a")
d.arc((8, 10, 14, 16), 200, 340, fill="#6b3a1a", width=1)    # two happy shut eyes
d.arc((17, 10, 23, 16), 200, 340, fill="#6b3a1a", width=1)
d.ellipse((6, 16, 10, 19), fill="#ff9aa8")                   # blush
d.ellipse((21, 16, 25, 19), fill="#ff9aa8")
d.arc((11, 15, 20, 24), 20, 160, fill="#6b3a1a", width=1)    # smile
im.save(os.path.join(HERE, "art", "wheel_sheet.png"))
json.dump({"format": "mei-sheet", "version": 1, "cells": {"sun": [0, 0, 32, 32]}},
          open(os.path.join(HERE, "art", "wheel_sheet.sheet.json"), "w"), indent=2)

# ---------------------------------------------------------------- geometry
CY = 13.6            # hub height
RC = 10.6            # rim centre-line radius
RO, RI = 10.85, 10.35
ZR = 1.1             # rims at z = +-ZR
HT = 0.2             # half thickness of a rim along z
N = 16
STEP = 360.0 / N

def rim_mesh():
    verts, faces, mats = [], [], []
    for zc in (-ZR, ZR):
        base = len(verts)
        for k in range(N):
            a = math.radians(k * STEP)
            c, s = math.cos(a), math.sin(a)
            for r in (RO, RI):
                for z in (zc - HT, zc + HT):
                    verts.append([round(r * c, 4), round(CY + r * s, 4), z])
        def v(k, r, z):               # r: 0 outer, 1 inner; z: 0 front (-Z), 1 back
            return base + (k % N) * 4 + r * 2 + z
        for k in range(N):
            m = "rim_red" if k % 2 == 0 else "rim_cream"
            k2 = k + 1
            quads = [
                [v(k, 0, 0), v(k2, 0, 0), v(k2, 0, 1), v(k, 0, 1)],   # outer
                [v(k, 1, 1), v(k2, 1, 1), v(k2, 1, 0), v(k, 1, 0)],   # inner
                [v(k, 1, 0), v(k2, 1, 0), v(k2, 0, 0), v(k, 0, 0)],   # front
                [v(k, 0, 1), v(k2, 0, 1), v(k2, 1, 1), v(k, 1, 1)],   # back
            ]
            for q in quads:
                faces.append([q[0], q[1], q[2]]); mats.append(m)
                faces.append([q[0], q[2], q[3]]); mats.append(m)
    vol = 0.0
    for f in faces:
        p = [verts[i] for i in f]
        vol += (p[0][0] * (p[1][1] * p[2][2] - p[1][2] * p[2][1])
                - p[0][1] * (p[1][0] * p[2][2] - p[1][2] * p[2][0])
                + p[0][2] * (p[1][0] * p[2][1] - p[1][1] * p[2][0])) / 6
    if vol < 0:
        faces = [f[::-1] for f in faces]
    return {"id": "rims", "op": "mesh", "material": "rim_cream", "vertices": verts, "faces": faces,
            "face_materials": mats}

def box(i, size, mat, at, rot=None, **kw):
    t = {"translate": at}
    if rot:
        t["rotate"] = rot
    n = {"id": i, "op": "box", "size": size, "material": mat, "transform": t}
    n.update(kw)
    return n

BODIES = {  # name: (body, roof)
    "red": ("#d9453b", "#f4e8c8"),
    "yellow": ("#f2c230", "#d9453b"),
    "teal": ("#3fa69b", "#f4e8c8"),
    "pink": ("#ea7f9f", "#fff6e0"),
}
materials = {
    "rim_red": {"color": "#d9453b"},
    "rim_cream": {"color": "#f4e8c8"},
    "spoke": {"color": "#f4e8c8"},
    "frame": {"color": "#5f9fd0"},
    "frame_dark": {"color": "#3f6f9c"},
    "concrete": {"color": "#b4b0a4"},
    "pin": {"color": "#4a5864"},
    "sun": {"color": "#ffd84a", "texture": {"sheet": "sheet", "cell": "sun", "bits": 4, "projection": "disc", "axis": "y"}},
    "bulb": {"color": "#fff2a0", "class": "emissive"},
    "planks": {"color": "#b98962", "texture": {"pattern": "planks", "colors": ["#b98962", "#7d5634", "#a67a52", "#c79a73"],
               "params": {"boards": 4}, "projection": "box", "scale": [1.0, 1.0]}},
    "booth": {"color": "#f4e8c8"},
    "awning": {"color": "#d9453b", "texture": {"pattern": "stripes", "colors": ["#d9453b", "#f4e8c8"],
               "params": {"count": 4, "axis": "u"}, "projection": "box", "scale": [1.0, 1.0]}},
    "booth_roof": {"color": "#3f6f9c"},
}
for name, (body, roof) in BODIES.items():
    materials["cab_" + name] = {"color": body, "texture": {
        "texels": ["00000000", "01111110", "01232210", "01222210", "01111110", "00000000", "00000000", "00000000"],
        "colors": [body, "#fff6e0", "#8ec9e0", "#ffffff"], "projection": "box", "scale": [1.5, 1.3],
        "offset": [0.5, 0.5]}}
    materials["roof_" + name] = {"color": roof}

prototypes = {}
for name in BODIES:
    prototypes["gondola_" + name] = {"op": "group", "children": [
        box("pin", [0.14, 0.14, 2.2], "pin", [0, 0, 0], open=["front", "back"]),
        box("hanger", [0.1, 0.65, 0.1], "pin", [0, -0.4, 0], open=["top", "bottom"]),
        {"id": "roof", "op": "cone", "radius": 1.05, "height": 0.5, "segments": 6, "material": "roof_" + name,
         "transform": {"translate": [0, -0.5, 0]}},
        box("cabin", [1.5, 1.3, 1.5], "cab_" + name, [0, -1.37, 0], open=["bottom"]),
    ]}

nodes = [rim_mesh()]
# spokes: sixteen to a side
nodes.append({"id": "spokes", "op": "group", "transform": {"translate": [0, CY, 0]}, "children": [
    box("spoke_front", [9.4, 0.16, 0.16], "spoke", [5.95, 0, -ZR], open=["left", "right"]),
    box("spoke_back", [9.4, 0.16, 0.16], "spoke", [5.95, 0, ZR], open=["left", "right"])],
    "modifiers": [{"op": "radial", "count": N, "axis": "z"}]})
# hub with the sun on it, axle
nodes.append({"id": "hub", "op": "cylinder", "radius": 1.3, "height": 3.0, "segments": 12, "material": "sun",
              "transform": {"rotate": [-90, 0, 0], "translate": [0, CY, 0]}})
nodes.append({"id": "axle", "op": "cylinder", "radius": 0.22, "height": 4.2, "segments": 8, "caps": False,
              "material": "frame_dark", "transform": {"rotate": [90, 0, 0], "translate": [0, CY, 0]}})
# the A-frames (one at z = +1.9, mirrored to -1.9)
lean = math.degrees(math.atan2(6.0, CY))
leg_len = math.hypot(6.0, CY)
nodes.append({"id": "frames", "op": "group", "modifiers": [{"op": "mirror", "axis": "z"}], "children": [
    box("leg_l", [0.5, leg_len, 0.5], "frame", [-3.0, CY / 2, 1.9], rot=[0, 0, -lean], open=["bottom", "top"]),
    box("leg_r", [0.5, leg_len, 0.44], "frame", [3.0, CY / 2, 1.9], rot=[0, 0, lean], open=["bottom", "top"]),
    box("brace", [7.6, 0.3, 0.3], "frame_dark", [0, 5.0, 1.9]),
    box("foot_l", [1.3, 0.4, 1.0], "concrete", [-6.0, 0.2, 1.9], open=["bottom"]),
    box("foot_r", [1.3, 0.4, 1.0], "concrete", [6.0, 0.2, 1.9], open=["bottom"]),
]})
nodes.append({"id": "ties", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}], "children": [
    box("tie", [0.5, 0.3, 3.8], "frame_dark", [6.0, 0.5, 0.0]),
    box("tie_mid", [0.4, 0.24, 3.8], "frame_dark", [3.79, 5.0, 0.0])]})
# gondolas
names = list(BODIES)
for k in range(N):
    a = math.radians(k * STEP)
    nodes.append({"id": "gondola_%d" % k, "op": "instance", "ref": "gondola_" + names[k % 4],
                  "transform": {"translate": [round(RC * math.cos(a), 4), round(CY + RC * math.sin(a), 4), 0]}})
# bulbs on the front rim, between the gondolas
for k in range(N):
    a = math.radians((k + 0.5) * STEP)
    nodes.append({"id": "bulb_%d" % k, "op": "sphere", "radius": 0.2, "rings": 2, "segments": 4, "material": "bulb",
                  "transform": {"translate": [round(RC * math.cos(a), 4), round(CY + RC * math.sin(a), 4), -ZR - HT - 0.05]}})
# boarding platform and ticket booth
nodes.append(box("platform", [5.0, 0.9, 2.6], "planks", [0, 0.45, -2.6], open=["bottom"]))
nodes.append(box("step", [2.4, 0.45, 0.6], "planks", [0, 0.225, -4.1], open=["bottom"]))
nodes.append(box("booth", [2.4, 2.0, 2.0], "booth", [8.5, 1.0, -3.0], open=["bottom"]))
nodes.append({"id": "booth_roof", "op": "cone", "radius": 2.0, "height": 1.0, "segments": 4, "material": "booth_roof",
              "transform": {"rotate": [0, 45, 0], "translate": [8.5, 2.48, -3.0]}})
nodes.append(box("awning", [2.8, 0.08, 0.9], "awning", [8.5, 1.9, -4.4], rot=[-14, 0, 0]))

recipe = {
    "format": "mei-asset", "version": 1, "name": "ferris_wheel",
    "budget": {"vertices": 1600, "triangles": 1800},
    "sheets": {"sheet": {"image": "art/wheel_sheet.png"}},
    "materials": materials,
    "prototypes": prototypes,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
json.dump(recipe, open(os.path.join(HERE, "ferris_wheel.asset.json"), "w"), indent=1)
