#!/usr/bin/env python3
"""Writes sento_front.asset.json. The recipe is the source of truth; this script only computes
its coordinates (the curved roof, hand-placed quads) so they need not be typed by hand.

The sento faces -Z. Y is up; one unit is about a metre. The front is at z = -4.2 (the wall),
the entrance porch reaches z = -6.6, the boiler annex and its chimney stand on the +X side."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
nodes = []


seen = {}


def add(n):
    """Append a node; sibling ids must differ, so repeated ids get _2, _3, ..."""
    k = seen.get(n["id"], 0) + 1
    seen[n["id"]] = k
    if k > 1:
        n["id"] = "%s_%d" % (n["id"], k)
    nodes.append(n)
    return n


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def dot(a, b): return sum(a[i]*b[i] for i in range(3))
def r(v): return [round(x, 4) for x in v]


def poly(id_, mat, verts, faces, outward, uvs=None, extra=None):
    """A mesh whose faces are wound so each normal points along `outward` (a vector, or a
    point the faces should face away from when given as ('away', point))."""
    out = []
    for f in faces:
        a, b, c = (verts[f[0]], verts[f[1]], verts[f[2]])
        n = cross(sub(b, a), sub(c, a))
        if isinstance(outward, tuple):
            ctr = [sum(verts[i][k] for i in f) / len(f) for k in range(3)]
            ref = sub(ctr, outward[1])
        else:
            ref = outward
        out.append(list(f) if dot(n, ref) >= 0 else list(reversed(f)))
    node = {"id": id_, "op": "mesh", "material": mat, "vertices": [r(v) for v in verts], "faces": out}
    if uvs:
        node["uvs"] = uvs
    if extra:
        node.update(extra)
    return node


def vquad(id_, mat, cx, cy, cz, w, h, facing, extra=None):
    """A vertical quad centred on (cx, cy, cz): facing -z, +z, -x or +x."""
    hw, hh = w / 2, h / 2
    if facing in ("-z", "+z"):
        v = [[cx - hw, cy - hh, cz], [cx + hw, cy - hh, cz], [cx + hw, cy + hh, cz], [cx - hw, cy + hh, cz]]
        n = [0, 0, -1 if facing == "-z" else 1]
    else:
        v = [[cx, cy - hh, cz - hw], [cx, cy - hh, cz + hw], [cx, cy + hh, cz + hw], [cx, cy + hh, cz - hw]]
        n = [-1 if facing == "-x" else 1, 0, 0]
    return poly(id_, mat, v, [[0, 1, 2, 3]], n, extra=extra)


def box(id_, mat, size, at, open_=None, rot=None, mods=None):
    n = {"id": id_, "op": "box", "size": size, "material": mat, "transform": {"translate": at}}
    if rot:
        n["transform"]["rotate"] = rot
    if open_:
        n["open"] = open_
    if mods:
        n["modifiers"] = mods
    return n


M = {}
M["stone"] = {"color": "#8e8e86", "tag": "floor", "texture": {
    "pattern": "tile", "colors": ["#9a9a92", "#5f5f5b", "#8a8a84"], "params": {"count": 2, "grout": 1},
    "projection": "box", "scale": [1.6, 1.6]}}
M["shingle"] = {"color": "#4a5668", "tag": "roof", "texture": {
    "texels": ["01210121", "01210121", "01210121", "33333333"] * 2,
    "colors": ["#2f3846", "#4b586c", "#7385a2", "#1b212b"], "projection": "planar", "axis": "y",
    "scale": [1.2, 1.2]}}
M["shingle_k"] = {"color": "#4a5668", "tag": "roof", "texture": {
    "texels": ["01210121", "01210121", "01210121", "33333333"] * 2,
    "colors": ["#2f3846", "#4b586c", "#7385a2", "#1b212b"], "projection": "planar", "axis": "y",
    "scale": [1.2, 1.2]}}
M["plaster"] = {"color": "#ddd5c0", "tag": "wall", "texture": {
    "pattern": "speckle", "colors": ["#ddd5c0", "#cdc3aa", "#e8e2d2"], "params": {"density": 0.14, "seed": 3},
    "projection": "box", "scale": [2.0, 2.0]}}
M["wood_low"] = {"color": "#6b4a34", "tag": "wall", "texture": {
    "pattern": "stripes", "colors": ["#76523a", "#6a4932", "#5c3f2a", "#6a4932"], "params": {"count": 8},
    "projection": "box", "scale": [1.6, 1.6]}}
M["beam"] = {"color": "#4a3020", "texture": {
    "pattern": "stripes", "colors": ["#5e3f2a", "#4c3220", "#563826", "#4c3220"], "params": {"count": 4},
    "projection": "box", "scale": [0.8, 0.8]}}
M["post"] = {"color": "#4a3020", "texture": {
    "pattern": "stripes", "colors": ["#5e3f2a", "#4c3220", "#563826", "#4c3220"], "params": {"count": 4},
    "projection": "cylindrical", "scale": [0.8, 0.8]}}
M["brick"] = {"color": "#9c4f34", "tag": "wall", "texture": {
    "pattern": "brick", "colors": ["#a4553a", "#b99a7a", "#94492f"], "params": {"courses": 4, "bricks": 2},
    "projection": "box", "scale": [1.2, 0.9]}}
M["glass_door"] = {"color": "#f6ecb4", "class": "emissive", "tag": "door", "texture": {
    "pattern": "lattice", "colors": ["#5a3d28", "#f2e6a8"], "params": {"count": 2, "bar": 1},
    "projection": "fit"}}
M["glass_win"] = {"color": "#d6ecf0", "class": "emissive", "tag": "window", "texture": {
    "pattern": "lattice", "colors": ["#4c4a46", "#c8e4ea"], "params": {"count": 4, "bar": 1},
    "projection": "fit"}}
M["glass_win_up"] = {"color": "#f6e6a0", "class": "emissive", "tag": "window", "texture": {
    "pattern": "lattice", "colors": ["#4c4a46", "#f0e2a0"], "params": {"count": 4, "bar": 1},
    "projection": "fit"}}
sheet = lambda cell, **kw: dict({"sheet": "s", "cell": cell, "bits": 4, "projection": "fit"}, **kw)
M["noren_blue"] = {"color": "#2c4d92", "double_sided": True, "texture": sheet("noren_blue")}
M["noren_red"] = {"color": "#b8352f", "double_sided": True, "texture": sheet("noren_red")}
M["plaque"] = {"color": "#22397a", "texture": sheet("plaque")}
M["chochin"] = {"color": "#c63a2c", "class": "emissive", "texture": sheet("chochin", projection="cylindrical", scale=[1.0, 0.5])}
M["vend"] = {"color": "#c8322a", "class": "emissive", "texture": sheet("vend")}
M["kanban"] = {"color": "#ece4cc", "double_sided": True, "texture": sheet("kanban")}
M["nobori"] = {"color": "#c8322a", "double_sided": True, "texture": sheet("nobori")}
M["bike"] = {"color": "#2f8f86", "double_sided": True, "texture": sheet("bike", bits=4)}
M["steam"] = {"color": "#f2f4f6", "class": "emissive", "double_sided": True, "texture": sheet("steam")}
M["yu_red"] = {"color": "#c8322a", "texture": sheet("yu_red")}
for name, col in {"fascia": "#39404c", "dark": "#2a2624", "cap": "#262c36", "white": "#eae6d8",
                  "pot": "#b0603c", "leaf": "#4f8a4a", "leaf2": "#3d7440", "granite": "#9c9a94",
                  "granite_d": "#74726e", "cat": "#d8923c", "cat_w": "#f0e6d0", "cat_d": "#8c5424",
                  "pink": "#e8a0a0", "vend_body": "#a8322a", "door_dark": "#4a3626", "pole": "#7a6a58",
                  "soil": "#4a3424", "step": "#a8a8a0"}.items():
    M[name] = {"color": col}

# ---------------------------------------------------------------- foundation and walls
PL_Y = 0.5
add(box("plinth", "stone", [17.8, PL_Y, 9.4], [0, PL_Y / 2, 0], ["bottom"]))
add(box("platform", "stone", [7.2, 0.45, 2.4], [0, 0.225, -5.75], ["bottom"]))
add(box("step", "stone", [5.0, 0.22, 0.95], [0, 0.11, -7.325], ["bottom"]))
add(box("wall_low", "wood_low", [16, 1.2, 8.4], [0, 1.1, 0], ["bottom", "top"]))
add(box("wall_mid", "plaster", [16, 2.3, 8.4], [0, 2.85, 0], ["bottom", "top"]))
add(box("trim_low", "beam", [16.24, 0.16, 8.64], [0, 1.7, 0]))
add(box("wall_up", "plaster", [12, 1.8, 5.6], [0, 6.0, 0], ["bottom", "top"]))
add(box("trim_up", "beam", [12.24, 0.18, 5.84], [0, 5.3, 0]))

# lower skirt roof (mokoshi) around the ground floor, and its soffit
SO = (8.9, 5.1, 4.2)       # outer half-width, half-depth, y of the skirt's outer edge
SI = (6.0, 2.8, 5.1)       # inner half-width, half-depth, y where it meets the upper wall
sk_v = [[-SO[0], SO[2], -SO[1]], [SO[0], SO[2], -SO[1]], [SO[0], SO[2], SO[1]], [-SO[0], SO[2], SO[1]],
        [-SI[0], SI[2], -SI[1]], [SI[0], SI[2], -SI[1]], [SI[0], SI[2], SI[1]], [-SI[0], SI[2], SI[1]]]
sk_f = [[0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
add(poly("skirt", "shingle", sk_v, sk_f, ("away", [0, 0, 0])))
fz = 0.3   # fascia height
fas_v = [[-SO[0], SO[2] - fz, -SO[1]], [SO[0], SO[2] - fz, -SO[1]], [SO[0], SO[2] - fz, SO[1]], [-SO[0], SO[2] - fz, SO[1]]] + sk_v[:4]
fas_f = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
add(poly("skirt_fascia", "fascia", fas_v, fas_f, ("away", [0, 0, 0])))
add(poly("skirt_soffit", "fascia", fas_v[:4], [[0, 1, 2, 3]], [0, -1, 0]))

# main hip roof
RH, RE, RY, RT = (7.4, 4.4), 6.9, 9.4, 3.2
EO = [[-RH[0], RE, -RH[1]], [RH[0], RE, -RH[1]], [RH[0], RE, RH[1]], [-RH[0], RE, RH[1]]]
EU = [[x, RE + 0.34, z] for x, _, z in EO]
rf_v = EU + [[-RT, RY, 0], [RT, RY, 0]]
rf_f = [[0, 4, 5, 1], [2, 5, 4, 3], [3, 4, 0], [1, 5, 2]]
add(poly("roof", "shingle", rf_v, rf_f, ("away", [0, 5, 0])))
add(poly("roof_fascia", "fascia", EO + EU, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]], ("away", [0, 5, 0])))
add(poly("roof_soffit", "fascia", EO, [[0, 1, 2, 3]], [0, -1, 0]))
add(box("ridge", "cap", [7.0, 0.34, 0.5], [0, RY + 0.12, 0]))
for sx in (-1, 1):
    add(box("ridge_end", "granite_d", [0.5, 0.9, 0.56], [sx * 3.55, RY + 0.5, 0]))
    add(box("ridge_end_t", "granite_d", [0.34, 0.5, 0.34], [sx * 3.55, RY + 1.15, 0]))
# hip ridges: thin caps down the four corners
for sx in (-1, 1):
    for sz in (-1, 1):
        a = [sx * RT, RY, 0]
        b = [sx * RH[0], RE + 0.34, sz * RH[1]]
        mid = [(a[i] + b[i]) / 2 for i in range(3)]
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        ln = math.sqrt(dx * dx + dy * dy + dz * dz)
        yaw = math.degrees(math.atan2(dx, dz))
        pitch = -math.degrees(math.asin(dy / ln))
        add({"id": "hip_%s%s" % ("p" if sx > 0 else "m", "p" if sz > 0 else "m"), "op": "box",
             "size": [0.22, 0.18, round(ln, 3)], "material": "cap",
             "transform": {"rotate": [round(pitch, 3), round(yaw, 3), 0], "translate": r(mid)}})

# ---------------------------------------------------------------- karahafu over the entrance
ZF, ZB, YB, YBASE, HW = -6.6, -2.7, 6.55, 3.7, 4.2
N = 14
xs = [-HW + 2 * HW * i / N for i in range(N + 1)]


def curve(x):
    t = abs(x) / HW
    bell = (1 + math.cos(math.pi * t)) / 2
    return 4.25 + 1.8 * bell ** 1.25


top_v, top_f, top_uv = [], [], []
for x in xs:
    h = curve(x)
    top_v.append([x, h, ZF])
for x in xs:
    top_v.append([x, YB, ZB])
for i in range(N):
    a, b, c, d = i, i + 1, N + 1 + i + 1, N + 1 + i
    top_f += [[a, b, c], [a, c, d]]
for i, v in enumerate(top_v):
    x, y, z = v
    dist = 0.0 if z == ZF else math.sqrt((ZB - ZF) ** 2 + (YB - curve(xs[i - N - 1])) ** 2)
    top_uv.append([round(x / 1.2, 4), round(dist / 1.2, 4)])
add(poly("kara_top", "shingle_k", top_v, top_f, [0, 1, -0.2], uvs=top_uv))
fb_v = [[x, curve(x), ZF] for x in xs] + [[x, YBASE, ZF] for x in xs]
fb_f = []
for i in range(N):
    fb_f += [[i, N + 1 + i, N + 1 + i + 1], [i, N + 1 + i + 1, i + 1]]
add(poly("kara_board", "plaster", fb_v, fb_f, [0, 0, -1]))
un_v = [[x, YBASE, ZF] for x in xs] + [[-HW, YBASE, ZB], [HW, YBASE, ZB]]
un_f = [[N + 1, i, i + 1] for i in range(N)] + [[N + 1, N, N + 2]]
add(poly("kara_under", "fascia", un_v, un_f, [0, -1, 0]))
for sx in (-1, 1):
    add(poly("kara_side", "fascia", [[sx * HW, curve(HW), ZF], [sx * HW, YB, ZB], [sx * HW, YBASE, ZB], [sx * HW, YBASE, ZF]],
             [[0, 1, 2, 3]], [sx, 0, 0]))
# the gable's ornament: the hot-water plaque, and a thin beam along the board's bottom
add(vquad("kara_plaque", "plaque", 0, 4.95, ZF - 0.05, 1.5, 1.5, "-z"))
add(box("kara_lintel", "beam", [8.0, 0.3, 0.34], [0, YBASE - 0.02, ZF + 0.1]))

# porch posts, lintel, door frame, doors, noren
for sx in (-1, 1):
    add({"id": "post", "op": "cylinder", "radius": 0.15, "height": 3.1, "segments": 8, "caps": False,
         "material": "post", "transform": {"translate": [sx * 3.6, 0.6 + 1.55, -6.15]}})
    add(box("post_foot", "granite", [0.46, 0.2, 0.46], [sx * 3.6, 0.53, -6.15]))
add(box("door_frame", "beam", [6.0, 2.9, 0.22], [0, 1.9, -4.3]))
add(box("door_head", "beam", [6.4, 0.3, 0.32], [0, 3.45, -4.32]))
for sx in (-1, 1):
    add(vquad("door", "glass_door", sx * 1.65, 1.9, -4.43, 1.75, 2.45, "-z"))
    add(vquad("noren", "noren_blue" if sx < 0 else "noren_red", sx * 1.65, 2.0, -4.5, 1.7, 2.1, "-z"))
add(box("door_post", "beam", [0.16, 2.5, 0.16], [0, 1.9, -4.42]))
add(vquad("kanban_open", "kanban", 0, 2.7, -4.54, 1.0, 0.5, "-z"))

# hanging lanterns
for sx in (-1, 1):
    add({"id": "chochin", "op": "cylinder", "radius": 0.3, "height": 0.6, "segments": 8, "caps": False,
         "material": "chochin", "transform": {"translate": [sx * 3.0, 3.05, -6.2]}})
    add({"id": "chochin_cap", "op": "cone", "radius": 0.2, "height": 0.16, "segments": 8, "material": "dark",
         "transform": {"translate": [sx * 3.0, 3.43, -6.2]}})
    add({"id": "chochin_cord", "op": "cylinder", "radius": 0.025, "height": 0.2, "segments": 4, "caps": False,
         "material": "dark", "transform": {"translate": [sx * 3.0, 3.6, -6.2]}})

# ---------------------------------------------------------------- windows
for sx in (-1, 1):
    add(vquad("win_front", "glass_win", sx * 5.4, 2.8, -4.26, 2.0, 1.0, "-z"))
    add(box("win_front_sill", "beam", [2.3, 0.12, 0.3], [sx * 5.4, 2.22, -4.34]))
    add(box("win_front_head", "beam", [2.2, 0.1, 0.12], [sx * 5.4, 3.34, -4.25]))
    add(vquad("win_up_front", "glass_win_up", sx * 4.9, 6.1, -2.84, 1.6, 0.9, "-z"))
    add(vquad("win_up_back", "glass_win_up", sx * 3.0, 6.1, 2.84, 1.6, 0.9, "+z"))
    for sz in (-1, 1):
        add(vquad("win_end", "glass_win", sx * 8.06, 2.8, sz * 1.6, 1.6, 1.0, "-x" if sx < 0 else "+x"))
    add(vquad("win_up_end", "glass_win_up", sx * 6.06, 6.1, 0, 1.6, 0.9, "-x" if sx < 0 else "+x"))
    add(vquad("win_back", "glass_win", sx * 4.4, 2.8, 4.26, 2.0, 1.0, "+z"))
add(vquad("back_door", "door_dark", 0, 1.9, 4.26, 1.2, 2.2, "+z"))

# ---------------------------------------------------------------- boiler annex and chimney
AX, AZ = 10.7, 1.5
add(box("annex", "plaster", [3.2, 3.0, 5.2], [AX, 1.5, AZ], ["bottom"]))
add(box("annex_base", "stone", [3.4, 0.45, 5.4], [AX, 0.225, AZ], ["bottom"]))
add(box("annex_roof", "shingle", [4.0, 0.16, 6.2], [AX, 3.3, AZ], rot=[0, 0, -7]))
add(vquad("annex_door", "door_dark", AX, 1.1, AZ - 2.61, 1.0, 2.0, "-z"))
add(vquad("annex_win", "glass_win", AX - 1.61, 1.9, AZ + 0.5, 1.2, 0.8, "-x"))
CH_X, CH_Z, CH_Y0, CH_H, CH_W, TOP = 10.6, 2.6, 2.8, 10.8, 1.4, 0.74
add(box("chimney", "brick", [CH_W, CH_H, CH_W], [CH_X, CH_Y0 + CH_H / 2, CH_Z], ["bottom"],
        mods=[{"op": "taper", "top": TOP, "bottom": 1.0}]))


def chw(y):
    return CH_W * (1 + (TOP - 1.0) * (y - CH_Y0) / CH_H)


top_y = CH_Y0 + CH_H
add(box("chimney_band", "white", [chw(top_y - 1.0) + 0.14, 0.34, chw(top_y - 1.0) + 0.14], [CH_X, top_y - 1.0, CH_Z]))
add(box("chimney_cap", "dark", [chw(top_y) + 0.3, 0.3, chw(top_y) + 0.3], [CH_X, top_y + 0.1, CH_Z]))
EMY = 9.2
add(vquad("chimney_yu", "yu_red", CH_X, EMY, CH_Z - chw(EMY) / 2 - 0.04, 1.0, 1.0, "-z"))
for i, (dx, w) in enumerate([(0.0, 3.4), (0.7, 3.0), (-0.5, 2.6)]):
    add(vquad("steam_%d" % i, "steam", CH_X + dx, top_y + 1.4 + i * 1.3, CH_Z - 0.4 - i * 0.1, w, w * 0.5, "-z"))

# ---------------------------------------------------------------- street furniture
add(box("vend_body", "vend_body", [1.0, 1.9, 0.8], [-7.2, 0.95, -5.15]))
add(vquad("vend_front", "vend", -7.2, 1.0, -5.57, 0.85, 1.7, "-z"))
add(box("vend_top", "cap", [1.06, 0.1, 0.86], [-7.2, 1.96, -5.15]))

# stone lantern
add({"id": "toro", "op": "lathe", "segments": 6, "caps": True, "material": "granite",
     "profile": [[0.38, 0.0], [0.38, 0.14], [0.17, 0.2], [0.14, 0.7], [0.32, 0.78], [0.32, 0.9]],
     "transform": {"translate": [-5.2, 0.0, -7.0]}})
add({"id": "toro_fire", "op": "cylinder", "radius": 0.2, "height": 0.36, "segments": 6, "caps": True,
     "material": "granite_d", "transform": {"translate": [-5.2, 1.05, -7.0]}})
add({"id": "toro_roof", "op": "cone", "radius": 0.6, "height": 0.4, "segments": 6, "material": "granite",
     "transform": {"translate": [-5.2, 1.41, -7.0]}})
add({"id": "toro_top", "op": "sphere", "radius": 0.11, "rings": 3, "segments": 6, "material": "granite_d",
     "transform": {"translate": [-5.2, 1.72, -7.0]}})

# potted pine
add({"id": "pot", "op": "cylinder", "radius": 0.45, "height": 0.6, "segments": 8, "material": "pot",
     "transform": {"translate": [5.0, 0.3, -7.0]}})
add({"id": "pine_trunk", "op": "cylinder", "radius": 0.07, "height": 0.9, "segments": 5, "caps": False, "material": "beam",
     "transform": {"translate": [5.0, 0.95, -7.0]}})
for i, (dy, rad, col) in enumerate([(1.25, 0.62, "leaf2"), (1.7, 0.45, "leaf")]):
    add({"id": "pine_%d" % i, "op": "sphere", "radius": rad, "rings": 4, "segments": 8, "material": col,
         "transform": {"translate": [5.0, dy, -7.0], "scale": [1.2, 0.7, 1.2]}})

# nobori banner on a pole
add({"id": "nobori_pole", "op": "cylinder", "radius": 0.04, "height": 3.4, "segments": 5, "caps": False,
     "material": "pole", "transform": {"translate": [-3.9, 1.7, -7.5]}})
add(box("nobori_arm", "pole", [0.95, 0.05, 0.05], [-3.45, 3.3, -7.5]))
add(vquad("nobori", "nobori", -3.45, 1.85, -7.5, 0.9, 2.7, "-z"))

# bicycles
add({"id": "bike_a", "op": "group", "children": [vquad("bike_q", "bike", 0, 0.5, 0, 2.0, 1.0, "-z")],
     "transform": {"translate": [6.5, 0, -5.4]}})
add({"id": "bike_b", "op": "group", "children": [vquad("bike_q", "bike", 0, 0.5, 0, 2.0, 1.0, "-z")],
     "transform": {"rotate": [0, 38, 0], "translate": [4.5, 0, -5.8]}})

# hip caps on the skirt, ridge cap on the karahafu
def line_box(id_, mat, a, b, w=0.22, h=0.18):
    mid = [(a[i] + b[i]) / 2 for i in range(3)]
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    return {"id": id_, "op": "box", "size": [w, h, round(ln, 3)], "material": mat,
            "transform": {"rotate": [round(-math.degrees(math.asin(dy / ln)), 3), round(math.degrees(math.atan2(dx, dz)), 3), 0],
                          "translate": r(mid)}}


for sx in (-1, 1):
    for sz in (-1, 1):
        add(line_box("skirt_hip", "cap", [sx * SI[0], SI[2] + 0.09, sz * SI[1]], [sx * SO[0], SO[2] + 0.09, sz * SO[1]]))
add(line_box("kara_ridge", "cap", [0, curve(0) + 0.1, ZF], [0, YB + 0.1, ZB + 0.1], 0.3, 0.2))

# eave rafters under the front of the main roof
add({"id": "rafters", "op": "group", "children": [
    box("rafter", "beam", [0.16, 0.16, 1.6], [-6.3, 6.82, -3.5], ["top"])],
     "modifiers": [{"op": "array", "count": 10, "step": [1.4, 0, 0]}]})

# half-timbering on the upper front wall
for x in (-5.86, -3.6, -1.8, 0.0, 1.8, 3.6, 5.86):
    add(box("stud", "beam", [0.16, 1.4, 0.12], [x, 6.08, -2.84], ["back", "bottom", "top"]))
add(box("beam_up", "beam", [12.16, 0.16, 0.14], [0, 6.8, -2.84], ["back"]))

# a bench with milk bottles
BX, BZ = 8.0, -5.4
add(box("bench_seat", "beam", [1.7, 0.09, 0.5], [BX, 0.52, BZ]))
for sx in (-1, 1):
    add(box("bench_leg", "beam", [0.1, 0.48, 0.44], [BX + sx * 0.7, 0.24, BZ], ["bottom"]))
for i, col in enumerate(["white", "cat_d", "white"]):
    add({"id": "bottle", "op": "cylinder", "radius": 0.065, "height": 0.26, "segments": 5, "material": col,
         "transform": {"translate": [BX - 0.45 + i * 0.22, 0.69, BZ]}})

# the cat on the ridge
CX, CY, CZ = -1.0, RY + 0.29, 0.0
add({"id": "cat_body", "op": "sphere", "radius": 0.42, "rings": 4, "segments": 8, "material": "cat",
     "transform": {"translate": [CX, CY + 0.38, CZ], "scale": [1.0, 1.0, 1.15]}})
add({"id": "cat_head", "op": "sphere", "radius": 0.27, "rings": 3, "segments": 8, "material": "cat",
     "transform": {"translate": [CX, CY + 0.98, CZ - 0.12]}})
for sx in (-1, 1):
    add({"id": "cat_ear", "op": "cone", "radius": 0.1, "height": 0.2, "segments": 3, "material": "cat_d",
         "transform": {"translate": [CX + sx * 0.14, CY + 1.3, CZ - 0.12], "rotate": [0, 0, -sx * 12]}})
    add(box("cat_paw", "cat_w", [0.14, 0.2, 0.2], [CX + sx * 0.17, CY + 0.1, CZ - 0.42]))
add({"id": "cat_tail", "op": "cylinder", "radius": 0.06, "height": 0.8, "segments": 5, "caps": True, "material": "cat_d",
     "transform": {"translate": [CX + 0.18, CY + 0.18, CZ + 0.62], "rotate": [70, 0, 18]}})
add(box("cat_chest", "cat_w", [0.26, 0.4, 0.1], [CX, CY + 0.52, CZ - 0.43]))

recipe = {
    "format": "mei-asset", "version": 1, "name": "sento_front",
    "budget": {"vertices": 2000, "triangles": 1800},
    "sheets": {"s": {"image": "art/sento_sheet.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True, "scale": "world"},
    "nodes": nodes,
}
with open(os.path.join(HERE, "sento_front.asset.json"), "w") as fh:
    json.dump(recipe, fh, indent=1)
print(len(nodes), "nodes")
