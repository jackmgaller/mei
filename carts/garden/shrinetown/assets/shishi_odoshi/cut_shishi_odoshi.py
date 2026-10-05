#!/usr/bin/env python3
"""Cut the lab shishi-odoshi (examples/assets/lab/shishi_odoshi) to shrine town's 150 triangles.

Run from the repository root:
    python3 carts/garden/shrinetown/assets/shishi_odoshi/cut_shishi_odoshi.py
Reads the lab recipe, writes shishi_odoshi.asset.json and shishi_odoshi_col.asset.json beside
this file. art/leaves.png is the lab's own (a copy, with its make_art.py).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "..", "..", "..", "examples", "assets", "lab",
                   "shishi_odoshi", "shishi_odoshi.asset.json")
d = json.load(open(SRC))
d["budget"] = {"vertices": 150, "triangles": 150}
d["lighting"]["ambient"] = 0.5
by = {n["id"]: n for n in d["nodes"]}


def ngon(r, y, n, rev=False):
    pts = [[round(r * math.cos(2 * math.pi * i / n), 4), y, round(r * math.sin(2 * math.pi * i / n), 4)]
           for i in range(n)]
    return pts, list(range(n))[::-1] if rev else list(range(n))


# the gravel: one sheet
gravel = {"id": "gravel", "op": "mesh",
          "vertices": [[-0.75, 0.0, -0.3], [0.75, 0.0, -0.3], [0.75, 0.0, 0.3], [-0.75, 0.0, 0.3]],
          "faces": [[3, 2, 1, 0]], "material": "gravel"}
# the basin: an open-bottomed bowl with a flat top that the water sits on
basin = by["basin"]
basin.update(segments=6, caps=False, profile=[[0.26, 0.0], [0.27, 0.26], [0.0, 0.262]])
wv, wf = ngon(0.2, 0.0, 6, rev=True)
water = {"id": "basin_water", "op": "mesh", "vertices": wv, "faces": [wf], "material": "water",
         "transform": {"translate": [-0.5, 0.375, 0.02]}}
# the tilting tube
tube = by["tube"]
kids = {c["id"]: c for c in tube["children"]}
kids["wall"]["segments"] = 6
tv, tf = ngon(0.055, -0.45, 6)
kids["tail_cap"].update(vertices=tv, faces=[tf])
iv, iff = ngon(0.052, 0.31, 6, rev=True)
kids["inside"].update(vertices=iv, faces=[iff])
tube["children"] = [kids["wall"], kids["tail_cap"], kids["inside"]]
# the striking stone and the rock
by["strike_stone"].update(rings=2, segments=5)
rock = by["rock_back"]
rock.update(rings=2, segments=5)
rock["transform"]["translate"] = [-0.3871, 0.11, 0.25]
# bamboo posts as open-bottomed boxes
def post(i, h, at):
    return {"id": i, "op": "box", "size": [0.07, h, 0.07], "open": ["bottom"], "material": "bamboo",
            "transform": {"translate": at}}
up_f = post("upright_front", 0.56, [0.12, 0.28, -0.11])
up_b = post("upright_back", 0.56, [0.12, 0.28, 0.11])
src_post = post("source_post", 0.9, [-0.66, 0.45, 0.25])
pipe = by["source_pipe"]
pipe.update(segments=3, caps=True)
pipe["radius"] = 0.03
stream = by["stream"]
stream.update(open=["top", "bottom"])
# the frog: a body and two eye cones
frog = by["frog"]
frog.update(rings=2, segments=4)
eyes = []
for side, x in (("l", -0.522), ("r", -0.478)):
    eyes.append({"id": "frog_eye_" + side, "op": "cone", "radius": 0.018, "height": 0.03,
                 "segments": 3, "material": "frog_eye", "transform": {"translate": [x, 0.385, -0.205]}})
# two stalks with their leaf fans
for s in ("stalk_a", "stalk_c"):
    by[s].update(segments=4, caps=False)
nodes = [gravel, basin, water, tube, by["strike_stone"], up_f, up_b, src_post, pipe, stream, rock,
         frog] + eyes + [by["stalk_a"], by["stalk_a_leaf0"], by["stalk_a_leaf1"], by["stalk_c"],
                         by["stalk_c_leaf0"], by["stalk_c_leaf1"]]
d["nodes"] = nodes

# Level 1 (30 m): the basin, the tube on its posts, one stalk; gone from 70 m.
d["lod"] = {"levels": [{"distance": 30, "nodes": [
    {"id": "gravel", "op": "mesh", "vertices": gravel["vertices"], "faces": gravel["faces"],
     "material": "gravel"},
    basin, tube, up_f, up_b, by["stalk_a"], by["stalk_a_leaf0"], by["stalk_a_leaf1"]]}],
    "cull": 70}
json.dump(d, open(os.path.join(HERE, "shishi_odoshi.asset.json"), "w"), indent=1)


def box(i, size, at, rot=None):
    n = {"id": i, "op": "box", "size": size, "open": ["bottom"], "material": "solid",
         "transform": {"translate": at}}
    if rot:
        n["transform"]["rotate"] = rot
    return n


# Collision: the basin (a stepping block), the posts' frame and a floor sheet.
col = {"format": "mei-asset", "version": 1, "name": "shishi_odoshi_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": [
           box("basin", [0.56, 0.34, 0.56], [-0.5, 0.17, 0.02]),
           box("frame", [0.3, 0.56, 0.3], [0.12, 0.28, 0.0]),
           box("tube", [0.9, 0.2, 0.2], [0.08, 0.54, 0.0], [0, 0, -28]),
       ]}
json.dump(col, open(os.path.join(HERE, "shishi_odoshi_col.asset.json"), "w"), indent=1)
