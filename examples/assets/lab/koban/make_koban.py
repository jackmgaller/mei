#!/usr/bin/env python3
"""Writes koban.asset.json (the recipe is generated: tubes, slabs and cutout quads are explicit
meshes whose corners are computed here). Run: python3 examples/assets/lab/koban/make_koban.py

The koban faces -Z. Units are metres; the plinth is 4.3 m wide, the eaves 5 m.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def add(a, b): return [a[i] + b[i] for i in range(3)]
def sub(a, b): return [a[i] - b[i] for i in range(3)]
def mul(a, s): return [a[i] * s for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a):
    n = math.sqrt(dot(a, a))
    return [x / n for x in a]
def r5(v): return [round(x, 5) for x in v]


def oriented_box(id, c, ax, ay, az, hx, hy, hz, material, omit=(), transform=None):
    """A box as an explicit mesh: centre c, unit axes ax/ay/az, half sizes. omit names faces by
    the axis and sign, e.g. '+z'."""
    vs, idx = [], {}
    def v(sx, sy, sz):
        k = (sx, sy, sz)
        if k not in idx:
            idx[k] = len(vs)
            vs.append(r5(add(add(add(c, mul(ax, sx * hx)), mul(ay, sy * hy)), mul(az, sz * hz))))
        return idx[k]
    faces = []
    for name, axis, sign in (("x", 0, 1), ("x", 0, -1), ("y", 1, 1), ("y", 1, -1), ("z", 2, 1), ("z", 2, -1)):
        if ("+" if sign > 0 else "-") + name in omit:
            continue
        o = [(1, 1), (1, -1), (-1, -1), (-1, 1)]
        quad = []
        for a, b in o:
            s = [0, 0, 0]
            s[axis] = sign
            s[(axis + 1) % 3] = a
            s[(axis + 2) % 3] = b
            quad.append(v(*s))
        # orient outward
        p = [vs[i] for i in quad]
        n = cross(sub(p[1], p[0]), sub(p[2], p[0]))
        out = sub(mul(add(p[0], p[2]), 0.5), c)
        if dot(n, out) < 0:
            quad.reverse()
        faces.append(quad)
    node = {"id": id, "op": "mesh", "vertices": vs, "faces": faces, "material": material}
    if transform:
        node["transform"] = transform
    return node


def tube(id, p0, p1, w, material, caps=False, omit_end=()):
    d = norm(sub(p1, p0))
    up = [0, 1, 0] if abs(d[1]) < 0.9 else [1, 0, 0]
    u = norm(cross(d, up))
    vv = norm(cross(d, u))
    c = mul(add(p0, p1), 0.5)
    L = math.sqrt(dot(sub(p1, p0), sub(p1, p0))) / 2
    omit = tuple(omit_end) if caps else ("+z", "-z")
    return oriented_box(id, c, u, vv, d, w, w, L, material, omit)


def poly(id, pts, material, uvs=None):
    node = {"id": id, "op": "mesh", "vertices": [r5(p) for p in pts],
            "faces": [list(range(len(pts)))], "material": material}
    if uvs:
        node["uvs"] = [[round(a, 4), round(b, 4)] for a, b in uvs]
    return node


def quad_facing(id, c, right, up, w, h, material, flip=False):
    """A quad centred at c, seen from the side `right x up` points to: corners TL, BL, BR, TR."""
    tl = add(add(c, mul(right, -w / 2)), mul(up, h / 2))
    bl = add(add(c, mul(right, -w / 2)), mul(up, -h / 2))
    br = add(add(c, mul(right, w / 2)), mul(up, -h / 2))
    tr = add(add(c, mul(right, w / 2)), mul(up, h / 2))
    pts = [tl, bl, br, tr]
    return poly(id, pts, material)


def box(id, size, at, material, open=None, rotate=None):
    n = {"id": id, "op": "box", "size": size, "material": material,
         "transform": {"translate": at}}
    if open:
        n["open"] = open
    if rotate:
        n["transform"]["rotate"] = rotate
    return n


WALL_Z = -1.5   # the facade
nodes = []

# ---- base --------------------------------------------------------------------------------------
nodes.append(box("plinth", [4.3, 0.2, 3.3], [0, 0.1, 0], "concrete", ["bottom"]))
nodes.append(box("step", [1.5, 0.1, 0.5], [0.55, 0.05, -1.9], "concrete", ["bottom", "front"]))

# ---- body --------------------------------------------------------------------------------------
nodes.append(box("body", [4, 3.0, 3], [0, 1.7, 0], "wall", ["top", "bottom"]))
nodes.append(box("band", [4.06, 0.25, 3.06], [0, 3.075, 0], "police_blue", ["top", "bottom"]))
nodes.append(box("soffit", [5.0, 0.15, 4.0], [0, 3.275, 0], "fascia", ["top"]))

# ---- roof: a hip roof, tiles running down each slope ----------------------------------------------
E, R = 3.35, 4.85
roof_v = [[-2.5, E, -2.0], [2.5, E, -2.0], [2.5, E, 2.0], [-2.5, E, 2.0],
          [-0.5, R, 0.0], [0.5, R, 0.0]]
nodes.append({"id": "roof_front", "op": "mesh", "vertices": roof_v, "faces": [[0, 4, 5, 1]],
              "material": "roof_a"})
nodes.append({"id": "roof_back", "op": "mesh", "vertices": roof_v, "faces": [[2, 5, 4, 3]],
              "material": "roof_a"})
nodes.append({"id": "roof_left", "op": "mesh", "vertices": roof_v, "faces": [[3, 4, 0]],
              "material": "roof_b"})
nodes.append({"id": "roof_right", "op": "mesh", "vertices": roof_v, "faces": [[1, 5, 2]],
              "material": "roof_b"})
nodes.append(box("ridge", [1.2, 0.26, 0.24], [0, R + 0.02, 0], "roof_cap"))
for sx in (-1, 1):
    nodes.append(box("ridge_end_%s" % ("l" if sx < 0 else "r"), [0.14, 0.32, 0.26],
                     [sx * 0.66, R + 0.06, 0], "roof_cap"))

# ---- the front: window, door, signs ---------------------------------------------------------------
nodes.append(box("window", [1.1, 1.1, 0.06], [-0.9, 1.55, WALL_Z - 0.03], "window", ["front", "bottom"]))
nodes.append(box("sill", [1.3, 0.06, 0.2], [-0.9, 0.97, WALL_Z - 0.1], "fascia", ["front"]))
nodes.append(box("door", [1.1, 2.0, 0.06], [0.55, 1.2, WALL_Z - 0.03], "door", ["front", "bottom"]))
nodes.append(box("sign", [1.5, 0.5, 0.08], [0.55, 2.62, WALL_Z - 0.04], "sign", ["front"]))
nodes.append(box("board", [0.7, 1.0, 0.06], [1.5, 1.5, WALL_Z - 0.03], "board", ["front"]))
nodes.append(box("board_hood", [0.84, 0.05, 0.2], [1.5, 2.04, WALL_Z - 0.1], "fascia", ["front"]))

# red lamp on a bracket above the window
LZ = WALL_Z - 0.44
nodes.append(tube("lamp_arm", [-0.9, 2.5, WALL_Z], [-0.9, 2.5, LZ], 0.035, "iron", True, ("-z",)))
nodes.append({"id": "lamp_collar", "op": "cylinder", "radius": 0.11, "height": 0.07, "segments": 10,
              "material": "iron", "transform": {"translate": [-0.9, 2.36, LZ]}})
nodes.append({"id": "lamp", "op": "sphere", "radius": 0.25, "rings": 5, "segments": 10, "material": "lamp",
              "transform": {"translate": [-0.9, 2.65, LZ]}})
nodes.append({"id": "lamp_band", "op": "cylinder", "radius": 0.262, "height": 0.07, "segments": 10,
              "caps": False, "material": "lamp_band", "transform": {"translate": [-0.9, 2.65, LZ]}})
nodes.append({"id": "lamp_cap", "op": "cone", "radius": 0.14, "height": 0.12, "segments": 10,
              "material": "iron", "transform": {"translate": [-0.9, 2.96, LZ]}})

# downspouts at both front corners
for sx in (-1, 1):
    nodes.append(tube("spout_%s" % ("l" if sx < 0 else "r"), [sx * 1.93, 0.2, WALL_Z - 0.05],
                      [sx * 1.93, 2.95, WALL_Z - 0.05], 0.035, "iron"))

# ---- side walls --------------------------------------------------------------------------------
# right wall (+X): the mascot
nodes.append(quad_facing("mascot", [2.03, 1.75, 0.2], [0, 0, 1], [0, 1, 0], 1.0, 1.0, "mascot"))
nodes[-1]["vertices"] = [r5([2.03, 2.25, 0.7]), r5([2.03, 1.25, 0.7]), r5([2.03, 1.25, -0.3]), r5([2.03, 2.25, -0.3])]
# left wall (-X): an air-conditioner unit with its grille, and a pipe
nodes.append(box("ac", [0.28, 0.5, 0.75], [-2.14, 0.95, 0.3], "ac_body", ["right"]))
nodes.append({"id": "ac_grille", "op": "mesh", "material": "grille",
              "vertices": [r5([-2.285, 1.15, 0.55]), r5([-2.285, 0.75, 0.55]),
                           r5([-2.285, 0.75, 0.15]), r5([-2.285, 1.15, 0.15])],
              "faces": [[0, 1, 2, 3]]})
nodes.append(tube("ac_pipe", [-2.05, 0.95, -0.3], [-2.05, 3.0, -0.3], 0.025, "pipe"))
nodes.append(tube("ac_pipe_h", [-2.05, 0.95, -0.3], [-2.05, 0.95, 0.0], 0.021, "pipe"))

# ---- street furniture -----------------------------------------------------------------------------
# flowerpot and shrub beside the step
nodes.append({"id": "pot", "op": "cylinder", "radius": 0.17, "height": 0.34, "segments": 8, "material": "pot",
              "transform": {"translate": [1.75, 0.17, -1.9]}})
nodes.append({"id": "shrub", "op": "sphere", "radius": 0.27, "rings": 4, "segments": 8, "material": "leaf",
              "transform": {"translate": [1.75, 0.55, -1.9], "scale": [1, 1.1, 1]}})
nodes.append({"id": "shrub_top", "op": "sphere", "radius": 0.16, "rings": 3, "segments": 6, "material": "leaf_light",
              "transform": {"translate": [1.78, 0.82, -1.86]}})

# traffic cones
for i, (cx, cz) in enumerate(((1.25, -2.75), (1.95, -2.55))):
    nodes.append(box("cone_base_%d" % i, [0.3, 0.03, 0.3], [cx, 0.015, cz], "cone", ["bottom"]))
    nodes.append({"id": "cone_%d" % i, "op": "cone", "radius": 0.12, "height": 0.42, "segments": 8,
                  "caps": False, "material": "cone", "transform": {"translate": [cx, 0.24, cz]}})
    nodes.append({"id": "cone_ring_%d" % i, "op": "cylinder", "radius": 0.085, "height": 0.07, "segments": 8,
                  "caps": False, "material": "cone_band", "transform": {"translate": [cx, 0.27, cz]}})

# a wooden bench against the right wall, under the mascot
nodes.append(box("bench_seat", [0.42, 0.06, 1.3], [2.23, 0.5, 0.2], "bench"))
nodes.append(box("bench_back", [0.05, 0.38, 1.3], [2.025, 0.78, 0.2], "bench", ["left"]))
for i, z in enumerate((-0.35, 0.75)):
    nodes.append(box("bench_leg_%d" % i, [0.36, 0.47, 0.07], [2.24, 0.235, z], "iron", ["top", "bottom"]))

# the stop sign (止まれ), a pole and an inverted triangle
POLE = (2.6, -2.1)
nodes.append(tube("pole", [POLE[0], 0.0, POLE[1]], [POLE[0], 2.4, POLE[1]], 0.035, "pole"))
nodes.append({"id": "pole_cap", "op": "box", "size": [0.09, 0.05, 0.09], "material": "pole",
              "transform": {"translate": [POLE[0], 2.42, POLE[1]]}})
s = 0.45
nodes.append(poly("stop_sign",
                  [[POLE[0] - s, 2.4, POLE[1] - 0.06], [POLE[0] + s, 2.4, POLE[1] - 0.06],
                   [POLE[0], 2.4 - 0.9 * s * 2 * 0.5 * 1.0, POLE[1] - 0.06]],
                  "stop"))
nodes[-1]["vertices"].reverse()
nodes[-1]["uvs"] = [[0.5, 1.0], [1.0, 0.0], [0.0, 0.0]]

# sandwich board
fx, fz = -2.75, -2.3
for k, sgn in enumerate((-1, 1)):
    base = [fx, 0.0, fz + sgn * 0.3]
    top = [fx, 0.9, fz + sgn * 0.03]
    d = norm(sub(top, base))
    xax = [1, 0, 0]
    nax = norm(cross(xax, d))
    L = math.sqrt(dot(sub(top, base), sub(top, base)))
    n = oriented_box("aframe_%d" % k, mul(add(base, top), 0.5), xax, d, nax, 0.28, L / 2, 0.015,
                     "aframe")
    nodes.append(n)

# ---- a mamachari parked in front of the window --------------------------------------------------------
BZ, BX, BYAW = -2.0, -1.3, 0.0
def B(x, y, z=0.0): return [BX + x, y, BZ + z]
RW, FW = -0.52, 0.52
for nm, ax_ in (("wheel_r", RW), ("wheel_f", FW)):
    pts, uvs = [], []
    n = 12
    for i in range(n):
        t = 2 * math.pi * i / n + math.pi / 12
        pts.append(B(ax_ + 0.34 * math.cos(t), 0.34 + 0.34 * math.sin(t)))
        uvs.append((0.5 + 0.5 * math.cos(t), 0.5 - 0.5 * math.sin(t)))
    pts.reverse(); uvs.reverse()
    nodes.append(poly(nm, pts, "wheel", uvs))
bike_tubes = [
    ("seat_tube", B(-0.12, 0.3), B(-0.2, 0.9)),
    ("top_tube", B(-0.17, 0.74), B(0.36, 0.8)),
    ("down_tube", B(-0.12, 0.3), B(0.36, 0.72)),
    ("fork", B(0.42, 0.95), B(0.52, 0.34, 0.06)),
    ("fork_b", B(0.42, 0.95), B(0.52, 0.34, -0.06)),
    ("stay_a", B(-0.12, 0.3), B(-0.52, 0.34, 0.06)),
    ("stay_b", B(-0.12, 0.3), B(-0.52, 0.34, -0.06)),
    ("stem", B(0.4, 0.88), B(0.36, 1.06)),
    ("bars", B(0.36, 1.06, -0.3), B(0.36, 1.06, 0.3)),
]
for i, (nm, p0, p1) in enumerate(bike_tubes):
    nodes.append(tube("bike_" + nm, p0, p1, 0.014 + 0.0013 * i, "bike_frame"))
nodes.append(box("bike_saddle", [0.26, 0.05, 0.14], [BX - 0.2, 0.94, BZ], "bike_seat"))
nodes.append(box("bike_basket", [0.3, 0.22, 0.34], [BX + 0.66, 0.78, BZ], "basket", ["bottom"]))
nodes.append(box("bike_light", [0.06, 0.06, 0.06], [BX + 0.5, 0.9, BZ], "lamp"))

# ---- a traffic mirror on its own pole, behind the sandwich board
MX, MZ = -3.0, 0.9
nodes.append(tube("mirror_pole", [MX, 0.0, MZ], [MX, 2.9, MZ], 0.04, "pole"))
nodes.append({"id": "mirror_rim", "op": "cylinder", "radius": 0.4, "height": 0.07, "segments": 12,
              "material": "mirror_rim", "transform": {"rotate": [90, 0, 0], "translate": [MX, 2.55, MZ - 0.07]}})
mp = []
for i in range(12):
    t = 2 * math.pi * i / 12
    mp.append([MX + 0.33 * math.cos(t), 2.55 + 0.33 * math.sin(t), MZ - 0.115])
nodes.append(poly("mirror_face", mp, "mirror"))

# ---- the radio mast on the roof ------------------------------------------------------------------------
nodes.append(tube("mast", [-0.3, R + 0.1, 0.0], [-0.3, R + 1.0, 0.0], 0.025, "iron"))
for i, (y, w) in enumerate(((R + 0.9, 0.3), (R + 0.7, 0.22), (R + 0.5, 0.15))):
    nodes.append(tube("mast_arm_%d" % i, [-0.3, y, -w], [-0.3, y, w], 0.014, "iron"))

# ---- materials --------------------------------------------------------------------------------------
roof_texels = []
for y in range(16):
    row = ""
    for x in range(16):
        edge = (x % 4) in (3,)
        crest = (x % 4) in (1,)
        course = (y % 4) == 3
        if course:
            row += "3"
        elif edge:
            row += "2"
        elif crest:
            row += "1"
        else:
            row += "0"
    roof_texels.append(row)
roof_colors = ["#46505f", "#586373", "#2f3642", "#1f242d"]

materials = {
    "concrete": {"color": "#aaa79e",
                 "texture": {"pattern": "speckle", "colors": ["#aaa79e", "#8e8b83", "#c0bcb0"],
                             "params": {"density": 0.3}, "projection": "box", "scale": [1, 1]}},
    "wall": {"color": "#e6d9ba", "tag": "wall",
             "texture": {"pattern": "tile", "colors": ["#e6d9ba", "#c4b89a", "#dccfae"],
                         "params": {"count": 4, "grout": 1}, "projection": "box", "scale": [1, 1]}},
    "police_blue": {"color": "#2a4a82"},
    "fascia": {"color": "#d9cdb2"},
    "roof_a": {"color": "#46505f", "tag": "roof",
               "texture": {"texels": roof_texels, "colors": roof_colors, "projection": "planar",
                           "axis": "y", "scale": [1, 1]}},
    "roof_b": {"color": "#46505f", "tag": "roof",
               "texture": {"texels": roof_texels, "colors": roof_colors, "projection": "planar",
                           "axis": "y", "scale": [1, 1], "rotate": 90}},
    "roof_cap": {"color": "#2c323c"},
    "iron": {"color": "#33353a"},
    "pipe": {"color": "#b8bcc0"},
    "pole": {"color": "#d8d8d4"},
    "lamp": {"color": "#e8281e", "class": "emissive", "tag": "lamp"},
    "lamp_band": {"color": "#fff3d0", "class": "emissive", "tag": "lamp"},
    "cone": {"color": "#e85a1a"},
    "cone_band": {"color": "#f4f1e8"},
    "mirror_rim": {"color": "#e8801a"},
    "mirror": {"color": "#9cc4d6", "double_sided": True},
    "bench": {"color": "#a57a4e",
              "texture": {"pattern": "planks", "colors": ["#a57a4e", "#5a3c24", "#93693f", "#7d5634"],
                          "params": {"boards": 4}, "projection": "planar", "axis": "y", "scale": [1, 1]}},
    "pot": {"color": "#b86a3a"},
    "leaf": {"color": "#3f7d3a"},
    "leaf_light": {"color": "#6aa84a"},
    "ac_body": {"color": "#d6d8d4"},
    "bike_frame": {"color": "#2e3b52"},
    "bike_seat": {"color": "#1d1d20"},
    "window": {"color": "#274a5c", "texture": {"sheet": "art", "cell": "window", "bits": 8, "projection": "fit"}},
    "door": {"color": "#274a5c", "tag": "door",
             "texture": {"sheet": "art", "cell": "door", "bits": 8, "projection": "fit"}},
    "sign": {"color": "#1d3a6e",
             "texture": {"sheet": "art", "cell": "sign", "bits": 8, "projection": "fit"}},
    "board": {"color": "#b8895a",
              "texture": {"sheet": "art", "cell": "board", "bits": 8, "projection": "fit"}},
    "stop": {"color": "#c8201e", "double_sided": True,
             "texture": {"sheet": "art", "cell": "stop", "bits": 8, "projection": "fit"}},
    "mascot": {"color": "#fbe9c2", "double_sided": True,
               "texture": {"sheet": "art", "cell": "mascot", "bits": 8, "projection": "fit"}},
    "wheel": {"color": "#17171a", "double_sided": True,
              "texture": {"sheet": "art", "cell": "wheel", "projection": "fit"}},
    "aframe": {"color": "#f4f1e8",
               "texture": {"sheet": "art", "cell": "aframe", "bits": 8, "projection": "fit"}},
    "grille": {"color": "#d7d9d6",
               "texture": {"sheet": "art", "cell": "grille", "projection": "fit"}},
    "basket": {"color": "#b8bcc0", "double_sided": True,
               "texture": {"pattern": "lattice", "colors": ["#b8bcc0", "#000000"], "clear": "#000000",
                           "params": {"count": 2, "bar": 2}, "projection": "box", "scale": [0.3, 0.3]}},
}

recipe = {
    "format": "mei-asset", "version": 1, "name": "koban",
    "budget": {"vertices": 1400, "triangles": 1000},
    "sheets": {"art": {"image": "art/koban_sheet.png"}},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}

with open(os.path.join(HERE, "koban.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
