#!/usr/bin/env python3
"""Writes robot_plaza.asset.json (the recipe is plain JSON; this script is how it is authored)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
Y0 = 1.5  # top of the plinth: the robot's soles
HD = 0.7  # the head sits this much above the first design, over a taller scarf


def T(x=0, y=0, z=0, rot=None, pivot=None, scale=None):
    t = {"translate": [x, y, z]}
    if rot:
        t["rotate"] = list(rot)
    if pivot:
        t["pivot"] = list(pivot)
    if scale:
        t["scale"] = list(scale)
    return t


def box(i, sx, sy, sz, mat, x=0, y=0, z=0, rot=None, open_=None):
    n = {"id": i, "op": "box", "size": [sx, sy, sz], "material": mat, "transform": T(x, y, z, rot)}
    if open_:
        n["open"] = open_
    return n


def cyl(i, r, h, mat, x=0, y=0, z=0, rot=None, seg=10, caps=True):
    n = {"id": i, "op": "cylinder", "radius": r, "height": h, "segments": seg, "material": mat,
         "transform": T(x, y, z, rot)}
    if not caps:
        n["caps"] = False
    return n


def sph(i, r, mat, x=0, y=0, z=0, rings=3, seg=8, scale=None, rot=None):
    return {"id": i, "op": "sphere", "radius": r, "rings": rings, "segments": seg, "material": mat,
            "transform": T(x, y, z, rot, scale=scale)}


def grp(i, kids, x=0, y=0, z=0, rot=None, pivot=None, mods=None):
    n = {"id": i, "op": "group", "children": kids, "transform": T(x, y, z, rot, pivot)}
    if mods:
        n["modifiers"] = mods
    return n


def slab(i, x0, x1, y0, y1, z0, z1, mats, front="-z"):
    """A box as a mesh with a material per side: mats = dict side -> material, key 'rest'."""
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    quads = {"-z": [0, 3, 2, 1], "+z": [4, 5, 6, 7], "-x": [0, 4, 7, 3], "+x": [1, 2, 6, 5],
             "-y": [0, 1, 5, 4], "+y": [3, 7, 6, 2]}
    sides = ["-z", "+z", "-x", "+x", "-y", "+y"]
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    faces, fm = [], []
    for s in sides:
        q = quads[s]
        a, b, c = (v[q[0]], v[q[1]], v[q[2]])
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        wx, wy, wz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        outward = (a[0] - cx) * nx + (a[1] - cy) * ny + (a[2] - cz) * nz
        faces.append(q if outward > 0 else q[::-1])
        fm.append(mats.get(s, mats["rest"]))
    return {"id": i, "op": "mesh", "vertices": v, "faces": faces, "face_materials": fm,
            "material": mats["rest"]}


M = {}
M["shell"] = {"color": "#4aa3ad", "tag": "body",
              "texture": {"texels": ["1111111111111111"] + [
                  "1" + ("0" * 15) if r not in (2, 13) else "1" + "0" * 1 + "2" + "0" * 10 + "2" + "0" * 2
                  for r in range(1, 16)],
                  "colors": ["#4aa3ad", "#2f7480", "#c9efe8"], "projection": "box", "scale": [3.6, 3.6]}}
M["cream"] = {"color": "#efe3c4"}
M["orange"] = {"color": "#e8862a"}
M["dark"] = {"color": "#2f3b4a"}
M["gold"] = {"color": "#f2c230"}
M["scarf"] = {"color": "#d6403c",
              "texture": {"pattern": "stripes", "colors": ["#d6403c", "#fff0dc"], "params": {"count": 4, "axis": "v"},
                          "projection": "box", "scale": [1.2, 1.2]}}
M["face"] = {"color": "#1b2838", "class": "emissive",
             "texture": {"image": "art/face.png", "bits": 8, "projection": "fit"}}
M["badge"] = {"color": "#e8862a", "texture": {"image": "art/badge.png", "bits": 8, "projection": "disc", "axis": "y", "flip": "v"}}
M["beacon"] = {"color": "#ff9a3c", "class": "emissive"}
M["paving"] = {"color": "#c9bfae", "tag": "floor",
               "texture": {"pattern": "tile", "colors": ["#cdbfa9", "#a89b88", "#bfae96"],
                           "params": {"count": 2, "grout": 1}, "projection": "planar", "axis": "y", "scale": [2.4, 2.4]}}
M["inlay"] = {"color": "#8f8a96", "tag": "floor",
              "texture": {"pattern": "checker", "colors": ["#8d93a8", "#d9cfc0"], "params": {"count": 2},
                          "projection": "planar", "axis": "y", "scale": [1.5, 1.5]}}
M["stone"] = {"color": "#b9b2a6"}
M["stone_dark"] = {"color": "#8c867c"}
M["brick"] = {"color": "#a9553a", "tag": "wall",
              "texture": {"pattern": "brick", "colors": ["#a9553a", "#d9cdb4", "#93472f"],
                          "params": {"courses": 4, "bricks": 2}, "projection": "box", "scale": [1.0, 0.5]}}
M["wood"] = {"color": "#a9774a",
             "texture": {"pattern": "planks", "colors": ["#a9774a", "#5d3f26", "#97683c"],
                         "params": {"boards": 4}, "projection": "box", "scale": [1.0, 1.0]}}
M["trunk"] = {"color": "#6b4a36"}
M["leaf"] = {"color": "#5fa05a"}
M["ginkgo"] = {"color": "#e3b83a"}
M["blossom"] = {"color": "#f4aebd"}
M["hedge"] = {"color": "#3f7a4c"}
M["soil"] = {"color": "#6a4a38"}
M["flower_a"] = {"color": "#f2c230"}
M["flower_b"] = {"color": "#ee6f86"}
M["lamp"] = {"color": "#fff0b8", "class": "emissive"}
M["vend"] = {"color": "#d63a3a", "texture": {"image": "art/vending.png", "bits": 8, "projection": "fit"}}
M["vend_body"] = {"color": "#c23232"}
M["plaque"] = {"color": "#2d5a45", "texture": {"image": "art/plaque.png", "bits": 8, "projection": "fit"}}
M["bird"] = {"color": "#9aa3b3"}
M["bird_neck"] = {"color": "#5f9a86"}
M["beak"] = {"color": "#f2a23a"}

nodes = []

# ---- the plaza -------------------------------------------------------------------------------
nodes.append(box("floor", 30, 0.4, 30, "paving", 0, -0.2, 0, open_=["bottom", "left", "right", "back", "front"]))
nodes.append({"id": "inlay", "op": "cylinder", "radius": 9.5, "height": 0.2, "segments": 12, "material": "inlay",
              "transform": T(0, 0.0, 0)})

# plinth: two octagonal tiers and a plaque
nodes.append(cyl("plinth_low", 6.8, 1.0, "stone", 0, 0.3, 0, seg=8, caps=True))
nodes.append(cyl("plinth_up", 5.4, 0.8, "stone_dark", 0, 1.1, 0, seg=8))
nodes.append(cyl("plinth_rim", 5.9, 0.16, "cream", 0, 0.82, 0, seg=8))
nodes.append(slab("plaque", -1.5, 1.5, 0.45, 1.25, -7.15, -6.55, {"-z": "plaque", "rest": "dark"}))

# ---- the robot ----------------------------------------------------------------------------------
def leg(sx):
    return grp("leg_" + ("l" if sx < 0 else "r"), [
        box("foot", 3.4, 1.2, 5.0, "orange", 0, 0.55, -0.7),
        box("toe", 3.0, 0.8, 1.2, "dark", 0, 0.45, -3.2),
        {"id": "shin", "op": "cylinder", "radius": 0.9, "height": 2.7, "segments": 8, "material": "shell", "caps": False,
         "transform": T(0, 2.4, 0.2), "modifiers": [{"op": "taper", "top": 1.2, "bottom": 1.0}]},
        sph("knee", 1.15, "dark", 0, 3.8, 0.2),
        cyl("thigh", 1.0, 1.8, "shell", 0, 4.9, 0.2, seg=8, caps=False),
    ], x=sx, y=Y0)


nodes.append(leg(-2.2))
nodes.append(leg(2.2))

nodes.append(box("hip", 6.4, 1.5, 3.9, "cream", 0, Y0 + 6.1, 0.2))
nodes.append({"id": "torso", "op": "box", "size": [7.0, 4.7, 4.3], "material": "shell",
              "transform": T(0, Y0 + 8.7, 0.2), "modifiers": [{"op": "taper", "top": 1.2, "bottom": 0.82}]})
nodes.append(box("belt", 6.0, 0.55, 4.05, "orange", 0, Y0 + 6.9, 0.2))
nodes.append(box("buckle", 1.3, 0.9, 0.35, "gold", 0, Y0 + 6.9, -2.1))
# chest badge, a disc facing the front (-Z)
nodes.append(cyl("badge", 1.55, 0.5, "badge", 0, Y0 + 9.1, -2.0, rot=[90, 0, 0], seg=12))
nodes.append(box("collar", 4.6, 0.7, 3.2, "cream", 0, Y0 + 11.0, 0.2))
nodes.append(cyl("neck", 0.9, 1.8, "dark", 0, Y0 + 11.6, 0.1, seg=8, caps=False))

# the wind-up key on the back
key_outline = [[-0.4, -0.3], [-1.2, -1.0], [-2.2, -0.9], [-2.5, 0], [-2.2, 0.9], [-1.2, 1.0], [-0.4, 0.3],
               [0.4, 0.3], [1.2, 1.0], [2.2, 0.9], [2.5, 0], [2.2, -0.9], [1.2, -1.0], [0.4, -0.3]]
nodes.append(grp("key", [
    cyl("shaft", 0.32, 1.6, "dark", 0, 0, 0.0, rot=[90, 0, 0], seg=5, caps=False),
    {"id": "wings", "op": "extrude", "points": key_outline, "depth": 0.36, "material": "gold",
     "transform": T(0, 0, 0.85)},
], x=0, y=Y0 + 8.9, z=2.65, rot=[0, 0, 24]))

# scarf: a ring at the neck and two tails streaming down the back
nodes.append(cyl("scarf_ring", 2.25, 0.95, "scarf", 0, Y0 + 11.75, 0.1, seg=8, caps=False))
nodes.append(box("scarf_knot", 1.3, 1.3, 1.3, "scarf", 1.7, Y0 + 11.95, -1.7, rot=[0, 20, 0]))


def tail(i, x, z0, length, sway):
    secs = []
    n = 4
    for k in range(n + 1):
        y = -length * k / n
        zc = z0 + sway * (k / n) ** 1.3 * (1 if k % 2 == 0 else 1)
        xc = x + 0.6 * ((k % 2) * 2 - 1) * (k / n)
        w = 0.55
        secs.append({"y": round(-y, 3) * -1 if False else round(y, 3), "points": [
            [round(xc - w, 3), round(zc - 0.09, 3)], [round(xc + w, 3), round(zc - 0.09, 3)],
            [round(xc + w, 3), round(zc + 0.09, 3)], [round(xc - w, 3), round(zc + 0.09, 3)]]})
    secs.reverse()
    return {"id": i, "op": "loft", "sections": secs, "material": "scarf", "transform": T(0, 0, 0)}


nodes.append(grp("tails", [tail("tail_a", 3.0, 0.3, 6.0, 1.6), tail("tail_b", -3.0, 0.3, 4.6, 2.0)],
                 x=0, y=Y0 + 11.6, z=2.7))

# head
nodes.append({"id": "head", "op": "lathe", "segments": 10, "material": "cream",
              "profile": [[0, 0], [2.2, 0.05], [2.8, 0.5], [3.05, 1.4], [2.9, 2.3], [2.2, 3.0], [1.0, 3.35], [0, 3.45]],
              "transform": T(0, Y0 + 11.45 + HD, 0.2)})
nodes.append(slab("faceplate", -2.05, 2.05, Y0 + 12.1 + HD, Y0 + 14.3 + HD, -3.35, -1.3,
                  {"-z": "face", "rest": "dark"}))
for s, nm in ((-1, "l"), (1, "r")):
    nodes.append(cyl("ear_" + nm, 0.75, 1.3, "orange", s * 3.1, Y0 + 13.1 + HD, 0.2, rot=[0, 0, 90], seg=6))
    nodes.append(cyl("ear_cap_" + nm, 0.35, 1.7, "gold", s * 3.1, Y0 + 13.1 + HD, 0.2, rot=[0, 0, 90], seg=4))
nodes.append(cyl("antenna", 0.12, 1.5, "dark", 0, Y0 + 15.3 + HD, 0.2, seg=6, caps=False))
nodes.append(sph("beacon", 0.42, "beacon", 0, Y0 + 16.2 + HD, 0.2, rings=3, seg=8))

# arms. Hanging arm (robot's right, x < 0) and the waving arm (x > 0)
AU, AF = 2.6, 2.4  # upper arm and forearm lengths


def arm_parts(prefix):
    return [
        {"id": prefix + "_upper", "op": "cylinder", "radius": 0.8, "height": AU, "segments": 8, "material": "shell", "caps": False,
         "transform": T(0, -AU / 2 + 0.2, 0)},
        sph(prefix + "_elbow", 0.9, "dark", 0, -AU, 0),
    ]


def fore_parts(prefix):
    return [
        {"id": prefix + "_fore", "op": "cylinder", "radius": 0.72, "height": AF, "segments": 8, "material": "shell", "caps": False,
         "transform": T(0, -AF / 2 - AU, 0)},
        box(prefix + "_cuff", 1.7, 0.5, 1.7, "orange", 0, -AU - AF + 0.2, 0),
    ]


def hand(prefix, y, wave=False):
    if not wave:
        return grp(prefix + "_hand", [
            box("fist", 1.9, 1.7, 1.5, "cream", 0, -0.8, 0),
            box("thumb", 0.55, 0.9, 0.55, "cream", -1.1, -0.5, -0.3, rot=[0, 0, -20]),
        ], x=0, y=y, z=0)
    return grp(prefix + "_hand", [
        box("palm", 1.9, 1.5, 1.2, "cream", 0, -0.6, 0),
        box("f1", 0.8, 1.05, 0.55, "cream", -0.5, -1.5, 0),
        box("f3", 0.8, 1.25, 0.55, "cream", 0.5, -1.55, 0),
        box("thumb", 0.55, 0.9, 0.55, "cream", 1.15 if wave else -1.15, -0.5, -0.1, rot=[0, 0, 30 if wave else -30]),
    ], x=0, y=y, z=0)


# hanging arm
nodes.append(grp("arm_l", [
    sph("shoulder_l", 1.5, "orange", 0, 0, 0),
    *arm_parts("l"),
    *fore_parts("l"),
    hand("l", -AU - AF + 0.2),
], x=-4.85, y=Y0 + 10.1, z=0.2, rot=[0, 0, 5]))

# waving arm: the whole arm swung out and up, the forearm bent upward
nodes.append(grp("arm_r", [
    sph("shoulder_r", 1.5, "orange", 0, 0, 0),
    *arm_parts("r"),
    grp("r_forearm", [*fore_parts("r"), hand("r", -AU - AF + 0.2, True)], pivot=[0, -AU, 0], rot=[0, 0, 62]),
], x=4.85, y=Y0 + 10.1, z=0.2, rot=[0, 0, 104]))

# ---- the plaza's furniture ---------------------------------------------------------------------
def bench(i, x, z, yaw):
    return grp(i, [
        box("seat", 3.0, 0.16, 0.9, "wood", 0, 0.62, 0, open_=None),
        box("back", 3.0, 0.7, 0.14, "wood", 0, 1.1, 0.4),
        box("side_a", 0.18, 0.7, 0.8, "dark", -1.35, 0.3, 0, open_=["bottom"]),
        box("side_b", 0.18, 0.7, 0.8, "dark", 1.35, 0.3, 0, open_=["bottom"]),
    ], x=x, y=0, z=z, rot=[0, yaw, 0])


nodes += [bench("bench_a", -8.5, -9.5, -35), bench("bench_b", 9.0, -9.0, 40), bench("bench_c", 0, 10.5, 180)]

# lamp posts
for k, (lx, lz) in enumerate([(-11.2, -11.2), (11.2, -11.2), (-11.2, 11.2), (11.2, 11.2)]):
    nodes.append(grp("lamp_" + str(k), [
        cyl("pole", 0.14, 4.2, "dark", 0, 2.05, 0, seg=6, caps=False),
        box("lamp_head", 0.55, 0.55, 0.55, "lamp", 0, 4.35, 0),
        {"id": "lamp_roof", "op": "cone", "radius": 0.55, "height": 0.45, "segments": 4, "material": "dark",
         "transform": T(0, 4.8, 0, rot=[0, 45, 0])},
    ], x=lx, z=lz))

# trees: two blossom, one ginkgo, one green, at the corners of the back and sides
def tree(i, x, z, mat, r, h):
    return grp(i, [
        cyl("trunk", 0.32, h, "trunk", 0, h / 2 - 0.05, 0, seg=5, caps=False),
        sph("crown", r, mat, 0, h + r * 0.55, 0, rings=3, seg=8, scale=[1, 0.85, 1]),
    ], x=x, z=z)


nodes += [tree("tree_a", -12.6, 5, "blossom", 2.3, 3.2), tree("tree_b", 12.6, 5, "blossom", 2.1, 3.0),
          tree("tree_c", 12.8, -5.5, "ginkgo", 2.0, 3.6), tree("tree_d", -12.8, -5.5, "leaf", 2.0, 3.4)]

# back wall (brick, capped) with hedges
nodes.append(box("wall", 26, 1.3, 0.7, "brick", 0, 0.6, 14.4, open_=["bottom", "top"]))
nodes.append(box("wall_cap", 26.4, 0.18, 1.0, "stone", 0, 1.35, 14.4))
nodes.append(box("hedge_l", 7.0, 1.1, 1.2, "hedge", -9.5, 0.5, 12.9, open_=["bottom"]))
nodes.append(box("hedge_r", 7.0, 1.1, 1.2, "hedge", 9.5, 0.5, 12.9, open_=["bottom"]))

# flower beds beside the plinth steps
for k, (fx, fz, fm) in enumerate([(-6.5, -4.5, "flower_a"), (6.5, -4.5, "flower_b")]):
    nodes.append(grp("bed_" + str(k), [
        box("curb", 3.4, 0.4, 1.4, "soil", 0, 0.15, 0, open_=["bottom"]),
        sph("fl_1", 0.34, fm, -0.8, 0.5, 0, rings=2, seg=5),
        sph("fl_2", 0.34, fm, 0.2, 0.55, 0.1, rings=2, seg=5),
        sph("fl_3", 0.34, fm, 1.0, 0.5, -0.1, rings=2, seg=5),
    ], x=fx, z=fz))

# vending machine with a bin
nodes.append(grp("vending", [
    slab("vm", -0.6, 0.6, -0.05, 2.2, -0.45, 0.45, {"-z": "vend", "rest": "vend_body"}),
    cyl("bin", 0.35, 0.8, "dark", 1.2, 0.35, -0.1, seg=6),
], x=-10.5, z=9.5, rot=[0, 160, 0]))

# pigeons
def pigeon(i, x, y, z, yaw):
    return grp(i, [
        sph("body", 0.28, "bird", 0, 0.28, 0, rings=3, seg=6, scale=[0.85, 0.8, 1.3]),
        sph("head", 0.15, "bird_neck", 0, 0.52, -0.3, rings=2, seg=5),
    ], x=x, y=y, z=z, rot=[0, yaw, 0])


nodes += [pigeon("pigeon_a", -3.0, 0.0, -11.0, 20), pigeon("pigeon_b", 3.5, 0.0, -12.2, 200),
          pigeon("pigeon_c", -4.85, Y0 + 11.55, 0.2, -20)]

recipe = {
    "format": "mei-asset", "version": 1, "name": "robot_plaza",
    "budget": {"vertices": 1300, "triangles": 1900},
    "sheets": {},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
del recipe["sheets"]
with open(os.path.join(HERE, "robot_plaza.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
print("written", len(nodes), "nodes")
