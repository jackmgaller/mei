#!/usr/bin/env python3
"""Writes arch_komainu.asset.json and arch_komainu_col.asset.json (python3 gen_komainu.py).

A pair of guardian lion-dogs on plinths, facing -Z: the open-mouthed "a" lion at -X and the
closed-mouthed "un" lion at +X (as a visitor sees them from the approach)."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))


def lion(tag, x, open_mouth):
    def T(y, z, **k):
        return dict(translate=[x, y, z], **k)
    head_faces = {"back": "mouth"} if open_mouth else {}
    return [
        {"id": tag + "_plinth", "op": "box", "size": [0.8, 0.5, 0.9], "material": "stone",
         "open": ["bottom"], "transform": T(0.25, 0)},
        {"id": tag + "_haunch", "op": "box", "size": [0.64, 0.46, 0.5], "material": "stone",
         "open": ["bottom"], "modifiers": [{"op": "taper", "top": 0.7, "bottom": 1}],
         "transform": T(0.71, 0.15)},
        {"id": tag + "_chest", "op": "box", "size": [0.46, 0.7, 0.28], "material": "stone",
         "open": ["bottom"], "modifiers": [{"op": "taper", "top": 0.8, "bottom": 1}],
         "transform": T(0.83, -0.2)},
        {"id": tag + "_head", "op": "box", "size": [0.46, 0.36, 0.36], "material": "stone",
         "open": ["bottom"], "modifiers": [{"op": "taper", "top": 1, "bottom": 0.85}],
         "transform": T(1.28, -0.24)},
        {"id": tag + "_muzzle", "op": "box", "size": [0.26, 0.17, 0.2], "material": "stone",
         "open": ["bottom"], "faces": head_faces,
         "transform": T(1.26, -0.46)},
        {"id": tag + "_mane", "op": "box", "size": [0.66, 0.5, 0.22], "material": "mane",
         "open": ["bottom"], "modifiers": [{"op": "taper", "top": 1, "bottom": 0.9}],
         "transform": T(1.26, -0.02)},
    ]


nodes = lion("a", -0.55, True) + lion("un", 0.55, False)
recipe = {
    "format": "mei-asset", "version": 1, "name": "arch_komainu",
    "budget": {"triangles": 120},
    "materials": {
        "stone": {"color": "#a49e90", "texture": {"image": "art/forest_stone.png",
                  "projection": "box", "scale": [1.0, 1.0]}},
        "mouth": {"color": "#2c2a28", "palette": True},
        "mane": {"color": "#8e887c", "palette": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
    "lod": {"cull": 60},
}
col = {
    "format": "mei-asset", "version": 1, "name": "arch_komainu_col",
    "budget": {"triangles": 40},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "plinth_%s" % t, "op": "box", "size": [0.8, 0.5, 0.9], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [x, 0.25, 0]}}
        for t, x in (("a", -0.55), ("un", 0.55))
    ] + [
        {"id": "body_%s" % t, "op": "box", "size": [0.5, 0.9, 0.7], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [x, 0.93, -0.02]}}
        for t, x in (("a", -0.55), ("un", 0.55))
    ],
}
for name, r in (("arch_komainu", recipe), ("arch_komainu_col", col)):
    with open(os.path.join(here, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
