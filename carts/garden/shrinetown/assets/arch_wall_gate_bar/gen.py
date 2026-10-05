#!/usr/bin/env python3
"""Writes arch_wall_gate_bar (barred), arch_wall_gate_bar_lifted (the bar set down) and the
barred bar's collision.  Run: python3 gen.py   (the files land beside this script)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))

MATS = {
    "wood": {"color": "#8a6446",
             "texture": {"pattern": "grain", "size": 16, "colors": ["#8a6446", "#6a4a36", "#a07c58"],
                         "params": {"rings": 3, "waves": 1, "amplitude": 2},
                         "projection": "box", "scale": [1.0, 0.5]}},
    "wood_dark": {"color": "#5a3e2c", "palette": True},
}
POL = {"required": True, "depth": True, "perspective": True}
LIGHT = {"mode": "vertical", "ambient": 0.5}
LEN = 5.6   # x -2.8 .. 2.8; the last 0.3 m at each end sits in the gate posts' sockets


def parts(lifted):
    """Two beams and a stile.  Barred: standing in the opening.  Lifted: set down flat."""
    src = [("beam_0", [LEN, 0.22, 0.22], "wood", ["left", "right"], 1.0),
           ("beam_1", [LEN, 0.22, 0.22], "wood", ["left", "right"], 1.9),
           ("stile", [0.14, 1.1, 0.12], "wood_dark", ["top", "bottom"], 1.45)]
    out = []
    for nid, size, mat, op, y in src:
        n = {"id": nid, "op": "box", "size": size, "material": mat, "open": op}
        if not lifted:
            n["transform"] = {"translate": [0, y, 0]}
        else:   # turned about X: height becomes depth.  Lies on the ground, 1.2 m to the ridge side
            n["transform"] = {"rotate": [90, 0, 0], "translate": [0, 0.11, 1.2 + (y - 1.45)]}
        out.append(n)
    return out


def recipe(name, nodes, budget):
    return {"format": "mei-asset", "version": 1, "name": name, "budget": {"triangles": budget},
            "materials": MATS, "lighting": LIGHT, "verification": POL, "nodes": nodes}


def write(name, r):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")


barred = recipe("arch_wall_gate_bar", parts(False), 30)
barred["lod"] = {"levels": [{"distance": 30, "nodes": [
    {"id": "beam_0", "op": "box", "size": [LEN, 0.22, 0.22], "material": "wood",
     "open": ["left", "right", "top", "bottom"], "transform": {"translate": [0, 1.0, 0]}},
    {"id": "beam_1", "op": "box", "size": [LEN, 0.22, 0.22], "material": "wood",
     "open": ["left", "right", "top", "bottom"], "transform": {"translate": [0, 1.9, 0]}}]}],
    "cull": 90}
write("arch_wall_gate_bar", barred)
write("arch_wall_gate_bar_lifted", recipe("arch_wall_gate_bar_lifted", parts(True), 30))

# collision: the barred bar is a wall the width of the opening, 2.3 m tall, 0.3 m thick
col = {"format": "mei-asset", "version": 1, "name": "arch_wall_gate_bar_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}}, "lighting": LIGHT,
       "verification": POL,
       "nodes": [{"id": "wall", "op": "box", "size": [5.0, 2.3, 0.3], "material": "solid",
                  "transform": {"translate": [0, 1.15, 0]}}]}
write("arch_wall_gate_bar_col", col)
