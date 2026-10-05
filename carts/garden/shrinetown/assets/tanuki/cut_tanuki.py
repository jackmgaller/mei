#!/usr/bin/env python3
"""Cut the lab tanuki (examples/assets/lab/tanuki) to the shrine town's 150 triangles.

Run from the repository root: python3 carts/garden/shrinetown/assets/tanuki/cut_tanuki.py
Reads ../../../../../examples/assets/lab/tanuki/tanuki.asset.json, writes tanuki.asset.json
and tanuki_col.asset.json beside this file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "..", "..", "..", "examples", "assets", "lab", "tanuki",
                   "tanuki.asset.json")
d = json.load(open(SRC))
st = d["nodes"][0]
ch = {c["id"]: c for c in st["children"]}
ch["foot"] = ch["feet"]["children"][0]
d["budget"] = {"vertices": 140, "triangles": 150}

ch["belly"].update(rings=3, segments=6, radius=0.46)
ch["head"].update(rings=3, segments=8)
ch["faceplate"].update(rings=2, segments=6)
ch["tail"]["segments"] = 4
ch["tail"]["profile"] = [[0.001, 0.0], [0.17, 0.25], [0.001, 0.62]]
ch["bibband"]["segments"] = 6
ch["bibband"]["radius"] = 0.46
ch["plinth"] = {"id": "plinth", "op": "box", "size": [0.84, 0.14, 0.78], "open": ["bottom"],
                "material": "stone", "transform": {"translate": [0, 0.07, 0]}}
ch["bottle"]["segments"] = 4
ch["bottle"]["profile"] = [[0.08, 0], [0.04, 0.2], [0.04, 0.27]]
ch["leaf"]["points"] = [[0, 0.16], [0.09, -0.08], [-0.09, -0.08]]
st["children"] = [ch[i] for i in ("plinth", "belly", "head", "faceplate", "ears", "bibband",
                                  "tail", "bottle", "leaf")]
d["lighting"]["ambient"] = 0.5

# Level 1 (30 m): a plinth, a belly and a head; gone from 70 m.
d["lod"] = {"levels": [{"distance": 30, "nodes": [
    {"id": "plinth", "op": "box", "size": [0.76, 0.13, 0.7], "open": ["bottom"], "material": "stone",
     "transform": {"translate": [0, 0.065, 0]}},
    {"id": "belly", "op": "sphere", "radius": 0.4, "rings": 2, "segments": 5, "material": "glaze",
     "transform": {"translate": [0, 0.5, 0], "scale": [0.9, 1.1, 0.9]}},
    {"id": "head", "op": "sphere", "radius": 0.34, "rings": 2, "segments": 5, "material": "glaze",
     "transform": {"translate": [0, 1.08, 0], "scale": [1.0, 0.9, 0.9]}}]}], "cull": 70}
json.dump(d, open(os.path.join(HERE, "tanuki.asset.json"), "w"), indent=1)

col = {"format": "mei-asset", "version": 1, "name": "tanuki_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": [
           {"id": "body", "op": "box", "size": [0.76, 0.72, 0.7], "open": ["bottom"],
            "material": "solid", "transform": {"translate": [0, 0.36, 0]}},
           {"id": "head", "op": "box", "size": [0.6, 0.68, 0.58], "open": ["bottom"],
            "material": "solid", "transform": {"translate": [0, 1.06, 0]}}]}
json.dump(col, open(os.path.join(HERE, "tanuki_col.asset.json"), "w"), indent=1)
