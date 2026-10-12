#!/usr/bin/env python3
"""Writes watermill.asset.json, watermill_col.asset.json and watermill.cameras.json beside this
file: shrine town's watermill on the canal by the park, cut from the lab model
(examples/assets/lab/watermill) to the town's density limits and set on the canal's bank. Run
once and commit the outputs: python3 carts/garden/shrinetown/assets/watermill/make_watermill.py

Asset frame: origin at the centre of the footprint, the door facing -Z, the wheel on the +X side.
y = 0 is the park's ground (world 0.6); the bank's edge is at x = BANK + SHIFT[0] (1.73), and
everything beyond it (the wheel, its bearing post, the flume's trestles) stands in the canal,
down to its bed (y = -1.8, world -1.2): those parts lie below y = 0 on purpose. The wheel dips
0.45 m into the water (y = -1.0, world -0.4). Texture sheet: art/mill_sheet.png (the lab's, with
the wheel added by art/draw_mill.py).

The wheel is a band of boards between two cutout discs (rim, spokes, paddle tips): 28 triangles
where the lab's wheel had 608."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))


def r(v):
    return [round(x, 4) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def dot(a, b): return sum(a[i]*b[i] for i in range(3))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def orient(verts, faces, outward):
    """Wind each face so its normal points along `outward`: a vector, ('away', point), or
    a list of vectors, one a face."""
    out = []
    for k, f in enumerate(faces):
        pts = [verts[i] for i in f]
        n = newell(pts)
        if isinstance(outward, tuple):
            ctr = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
            ref = sub(ctr, outward[1])
        elif isinstance(outward[0], (list, tuple)):
            ref = outward[k]
        else:
            ref = outward
        out.append(list(f) if dot(n, ref) >= 0 else list(reversed(f)))
    return out


def mesh(id_, mat, verts, faces, outward, mats=None, uvs=None, decals=None):
    n = {"id": id_, "op": "mesh", "vertices": [r(v) for v in verts], "faces": orient(verts, faces, outward)}
    if mats:
        n["face_materials"] = mats
    else:
        n["material"] = mat
    if uvs:
        n["uvs"] = uvs
    if decals:
        n["decals"] = decals
    return n


def box(id_, mat, size, at, open_=None, faces=None, decals=None, rot=None, mods=None):
    n = {"id": id_, "op": "box", "size": r(list(size)), "material": mat, "transform": {"translate": r(list(at))}}
    if rot:
        n["transform"]["rotate"] = r(list(rot))
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    if mods:
        n["modifiers"] = mods
    return n


def cyl(id_, mat, radius, height, seg, at, caps=True, faces=None, rot=None):
    n = {"id": id_, "op": "cylinder", "radius": radius, "height": height, "segments": seg, "material": mat,
         "transform": {"translate": r(list(at))}}
    if not caps:
        n["caps"] = False
    if faces:
        n["faces"] = faces
    if rot:
        n["transform"]["rotate"] = list(rot)
    return n


def sphere(id_, mat, radius, seg, rings, at, scale=None):
    n = {"id": id_, "op": "sphere", "radius": radius, "segments": seg, "rings": rings, "material": mat,
         "transform": {"translate": r(list(at))}}
    if scale:
        n["transform"]["scale"] = list(scale)
    return n


def quad(id_, mat, cx, cy, cz, w, h, facing):
    """A vertical quad centred on (cx, cy, cz), facing -z, +z, -x or +x."""
    hw, hh = w / 2, h / 2
    if facing in ("-z", "+z"):
        v = [[cx - hw, cy - hh, cz], [cx + hw, cy - hh, cz], [cx + hw, cy + hh, cz], [cx - hw, cy + hh, cz]]
        n = [0, 0, -1 if facing == "-z" else 1]
    else:
        v = [[cx, cy - hh, cz - hw], [cx, cy - hh, cz + hw], [cx, cy + hh, cz + hw], [cx, cy + hh, cz - hw]]
        n = [-1 if facing == "-x" else 1, 0, 0]
    return mesh(id_, mat, v, [[0, 1, 2, 3]], n)


def strip(id_, mat, a, b, w, h):
    """A low gable cap (two sloping quads, 4 triangles) along the line a -> b, h above it."""
    d = sub(b, a)
    side = cross(d, [0, 1, 0])
    ln = math.sqrt(dot(side, side))
    side = [s / ln * w / 2 for s in side]
    v = [[a[0] + side[0], a[1], a[2] + side[2]], [b[0] + side[0], b[1], b[2] + side[2]],
         [b[0], b[1] + h, b[2]], [a[0], a[1] + h, a[2]],
         [a[0] - side[0], a[1], a[2] - side[2]], [b[0] - side[0], b[1], b[2] - side[2]]]
    return mesh(id_, mat, v, [[0, 1, 2, 3], [3, 2, 5, 4]], [[side[0], 1, side[2]], [-side[0], 1, -side[2]]])


def solid(id_, verts, faces):
    """A convex closed collision solid, its faces wound away from its centroid."""
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    return mesh(id_, "solid", verts, faces, ("away", c))


def cuboid(id_, x0, x1, y0, y1, z0, z1):
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
         [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def frustum(id_, lo, hi):
    """lo, hi: (half_x, half_z, y, cx, cz); a box-section frustum (also a tapered chimney)."""
    v = []
    for hx, hz, y, cx, cz in (lo, hi):
        v += [[cx - hx, y, cz - hz], [cx + hx, y, cz - hz], [cx + hx, y, cz + hz], [cx - hx, y, cz + hz]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def shift(nodes, dx, dz):
    for n in nodes:
        if "transform" in n:
            t = n["transform"].setdefault("translate", [0, 0, 0])
            n["transform"]["translate"] = r([t[0] + dx, t[1], t[2] + dz])
        elif n["op"] == "mesh":
            n["vertices"] = [r([v[0] + dx, v[1], v[2] + dz]) for v in n["vertices"]]
        else:
            n["transform"] = {"translate": [dx, 0, dz]}
    return nodes




# ------------------------------------------------------------------------------- materials
M = {
    "stone": {"color": "#8a8478", "texture": {
        "pattern": "brick", "colors": ["#8e887c", "#5a564e", "#a29c8c"], "params": {"courses": 4, "bricks": 2, "bond": 0.5},
        "projection": "box", "scale": [1.2, 0.6]}},
    "boards": {"color": "#6e4c2e", "tag": "wall", "texture": {
        "pattern": "planks", "colors": ["#6e4c2e", "#3a2818", "#5e4026", "#664629"], "params": {"boards": 4, "seed": 2},
        "projection": "box", "scale": [0.8, 0.8]}},
    "plaster": {"color": "#e8dcc0", "tag": "wall", "texture": {
        "pattern": "speckle", "colors": ["#ece4d2", "#dccfae"], "params": {"density": 0.15}, "projection": "box", "scale": [1, 1]}},
    "thatch": {"color": "#a3844c", "tag": "roof", "texture": {
        "pattern": "grain", "colors": ["#b8975a", "#7e6234", "#a3844c"], "params": {"rings": 4, "waves": 2, "amplitude": 2},
        "projection": "box", "scale": [1.0, 1.0]}},
    "door": {"color": "#6e4c2e", "tag": "door", "texture": {"sheet": "mill", "cell": "door", "projection": "fit"}},
    "window": {"color": "#efe6cc", "tag": "window", "texture": {"sheet": "mill", "cell": "window", "projection": "fit"}},
    "sign": {"color": "#d8c49a", "texture": {"sheet": "mill", "cell": "sign", "projection": "fit"}},
    "tawara": {"color": "#d8b86a", "texture": {"sheet": "mill", "cell": "tawara", "projection": "cylindrical", "scale": [0.36, 0.6]}},
    "water": {"color": "#3a7fa8", "tag": "water", "texture": {"sheet": "mill", "frames": ["water_0", "water_1", "water_2", "water_3"],
                                                              "ticks": 6, "projection": "planar", "axis": "y", "scale": [0.5, 0.5]}},
    "fall": {"color": "#7fb8d8", "double_sided": True, "texture": {"sheet": "mill", "frames": ["fall_0", "fall_1", "fall_2", "fall_3"],
                                                                  "ticks": 4, "projection": "fit"}},
    "wheel": {"color": "#5a3c24", "double_sided": True, "texture": {"sheet": "mill", "cell": "wheel", "projection": "fit"}},
}
# palette-backed colours (8 surface), from the shrine's palette
for name, col in {"timber": "#5a3e2c", "ridge": "#4a3a2e", "iron": "#3e4248", "band": "#8a6446",
                  "pin_red": "#d8462a", "pin_yellow": "#f0c030", "pin_blue": "#3a6ab0", "pin_green": "#40a060"}.items():
    M[name] = {"color": col, "palette": True}
M["stick"] = {"color": "#4a3a2e", "palette": True, "double_sided": True}
for k in ("pin_red", "pin_yellow", "pin_blue", "pin_green"):
    M[k]["double_sided"] = True

# ------------------------------------------------------------------------------- dimensions
# Design frame: the mill house centred near x = -0.2; the canal's bank edge at x = BANK (water to
# +X); the park's ground is y = 0, the canal's water y = -1.0 and its bed y = -1.8 (world 0.6,
# -0.4 and -1.2).
BANK, WATER, BED = 2.3, -1.0, -1.8
HX0, HX1, HZ = -1.7, 1.3, 1.4         # house walls
LOW_TOP, PLATE = 1.9, 2.7             # boards below, plaster above; wall plate
WX, WY, WR, WW = 2.75, 0.6, 1.8, 0.6  # wheel: centre x, centre y, rim radius, width (along x)
FL_Y, FL_Z0, FL_Z1 = 2.75, -0.3, 4.0  # flume: bottom y; spout end and far end along z
SHIFT = (-0.57, -0.85)


def house_upper(decals=True):
    v = [[HX0, PLATE, -HZ], [HX1, PLATE, -HZ], [HX1, LOW_TOP, -HZ], [HX0, LOW_TOP, -HZ],
         [HX0, LOW_TOP, HZ], [HX1, LOW_TOP, HZ], [HX1, PLATE, HZ], [HX0, PLATE, HZ], [HX0, 4.0, 0], [HX1, 4.0, 0]]
    f = [[0, 1, 2, 3], [4, 5, 6, 7], [3, 4, 7, 8, 0], [1, 9, 6, 5, 2]]
    n = mesh("walls_upper", "plaster", v, f, [[0, 0, -1], [0, 0, 1], [-1, 0, 0], [1, 0, 0]])
    if decals:
        n["decals"] = [{"id": "window_w", "face": 2, "material": "window", "size": [0.9, 0.6], "at": [0.0, 2.3]},
                       {"id": "window_n", "face": 1, "material": "window", "size": [0.9, 0.6], "at": [0.4, 2.3]}]
    return n


def roof(mat="thatch"):
    return {"id": "roof", "op": "extrude", "depth": 3.6, "material": mat,
            "points": [[-2, 0], [0, 1.8], [2, 0], [2, -0.3], [0, 1.5], [-2, -0.3]],
            "transform": {"rotate": [0, 90, 0], "translate": [-0.2, 2.45, 0]}}


def wheel(seg=12, band=True):
    out = []
    if band:
        out.append(cyl("wheel_band", "band", WR, WW, seg, [WX, WY, 0], caps=False, rot=[0, 0, 90]))
    for sx, nm in ((-1, "in"), (1, "out")):
        x = WX + sx * (WW / 2 + 0.02)
        out.append(mesh("wheel_" + nm, "wheel", [[x, WY - 2.05, -2.05], [x, WY - 2.05, 2.05], [x, WY + 2.05, 2.05],
                                                 [x, WY + 2.05, -2.05]], [[0, 1, 2, 3]], [sx, 0, 0]))
    return out


def flume(top="water"):
    return box("flume", "timber", [0.5, 0.25, FL_Z1 - FL_Z0], [WX, FL_Y + 0.125, (FL_Z0 + FL_Z1) / 2], faces={"top": top})


def fall():
    return mesh("fall", "fall", [[WX - 0.17, FL_Y + 0.25, FL_Z0], [WX + 0.17, FL_Y + 0.25, FL_Z0],
                                 [WX + 0.17, FL_Y - 0.05, FL_Z0 - 0.2], [WX - 0.17, FL_Y - 0.05, FL_Z0 - 0.2],
                                 [WX + 0.17, 2.2, -1.05], [WX - 0.17, 2.2, -1.05]],
                [[0, 1, 2, 3], [3, 2, 4, 5]], [[0, 0.5, -1], [0, 0.5, -1]])


def trestle(id_, z, braces=True):
    out = []
    for sx, nm in ((-1, "in"), (1, "out")):
        out.append(box("%s_leg_%s" % (id_, nm), "timber", [0.1, FL_Y - BED + 0.04, 0.1],
                       [WX + sx * 0.32, (FL_Y + 0.04 + BED) / 2, z], ["top", "bottom"]))
    out.append(box(id_ + "_cap", "timber", [0.84, 0.1, 0.18], [WX, FL_Y - 0.04, z]))
    if braces:
        out.append(box(id_ + "_brace", "timber", [0.6, 0.08, 0.03], [WX, 0.4, z], ["left", "right"]))
    return out


# ------------------------------------------------------------------------------- level 0
L0 = []
add = L0.append
add(box("foundation", "stone", [3.3, 0.45, 3.1], [-0.2, 0.225, 0], ["bottom"]))
add(box("walls_lower", "boards", [HX1 - HX0, LOW_TOP - 0.44, 2 * HZ], [-0.2, (LOW_TOP + 0.44) / 2, 0], ["top", "bottom"],
        decals=[{"id": "door", "face": "back", "material": "door", "size": [0.9, 1.36], "at": [-0.5, -0.03]},
                {"id": "sign", "face": "back", "material": "sign", "size": [0.22, 0.44], "at": [0.22, 0.38]}]))
add(house_upper())
for k, (x, z) in enumerate([(HX0, -HZ), (HX1, -HZ), (HX0, HZ), (HX1, HZ)]):
    add(box("post_%d" % k, "timber", [0.14, PLATE - 0.44, 0.14], [x, (PLATE + 0.44) / 2, z], ["top", "bottom"]))
for sz, nm in ((-1, "s"), (1, "n")):
    add(box("plate_" + nm, "timber", [HX1 - HX0 + 0.24, 0.12, 0.1], [-0.2, PLATE - 0.08, sz * (HZ + 0.1)]))
add(box("hood", "timber", [1.3, 0.05, 0.55], [-0.7, 1.98, -1.66], rot=[-18, 0, 0]))
add(roof())
add(box("ridge", "ridge", [3.7, 0.22, 0.42], [-0.2, 4.24, 0], ["bottom"]))
for k in range(4):                      # crossed sticks on the ridge, each pair two quads
    x = -1.55 + 0.9 * k
    for s, nm in ((1, "a"), (-1, "b")):
        a = math.radians(38) * s
        dz, dy = math.sin(a) * 0.31, math.cos(a) * 0.31
        add(mesh("stick_%d%s" % (k, nm), "stick", [[x - 0.035, 4.42 - dy, -dz], [x + 0.035, 4.42 - dy, -dz],
                                                   [x + 0.035, 4.42 + dy, dz], [x - 0.035, 4.42 + dy, dz]],
                 [[0, 1, 2, 3]], [0, -math.sin(a), math.cos(a)]))
# the pinwheel on the ridge's west end
add(box("pin_stick", "timber", [0.035, 0.85, 0.035], [-1.85, 4.63, 0.06], ["bottom"]))
add({"id": "pin_blades", "op": "mesh", "vertices": [[0.0837, 0.2153, 0], [0.42, 0, 0], [0, 0, 0], [-0.2153, 0.0837, 0], [0, 0.42, 0],
                                                    [-0.0837, -0.2153, 0], [-0.42, 0, 0], [0.2153, -0.0837, 0], [0, -0.42, 0]],
     "faces": [[0, 1, 2], [3, 4, 2], [5, 6, 2], [7, 8, 2]],
     "face_materials": ["pin_red", "pin_yellow", "pin_blue", "pin_green"],
     "transform": {"rotate": [0, 0, 15], "translate": [-1.85, 5.05, 0]}})
# rice bales by the door
for k, (x, y, z, yaw) in enumerate([(0.5, 0.23, -2.0, 0), (0.98, 0.23, -2.0, 0), (0.74, 0.62, -1.97, 4)]):
    add(cyl("bale_%d" % k, "tawara", 0.23, 0.6, 6, [x, y, z], rot=[90, yaw, 0]))
# the wheel over the canal, its axle and outboard bearing post, the flume on trestles
L0 += wheel()
add(cyl("axle", "iron", 0.07, 3.4 - HX1 + 0.05, 5, [(HX1 - 0.05 + 3.4) / 2, WY, 0], caps=False, rot=[0, 0, 90]))
add(box("bearing_post", "timber", [0.2, WY + 0.3 - BED, 0.2], [3.3, (WY + 0.3 + BED) / 2, 0], ["bottom"]))
add(flume())
add(fall())
L0 += trestle("trestle_a", 1.6)
L0 += trestle("trestle_b", 3.3)

# ------------------------------------------------------------------------------- level 1 (from 24 m)
L1 = [box("foundation", "stone", [3.3, 0.45, 3.1], [-0.2, 0.225, 0], ["bottom"]),
      box("walls_lower", "boards", [HX1 - HX0, LOW_TOP - 0.44, 2 * HZ], [-0.2, (LOW_TOP + 0.44) / 2, 0], ["top", "bottom"],
          decals=[{"id": "door", "face": "back", "material": "door", "size": [0.9, 1.36], "at": [-0.5, -0.03]}]),
      house_upper(False), roof(), box("ridge", "ridge", [3.7, 0.22, 0.42], [-0.2, 4.24, 0], ["bottom"]),
      {"id": "pin_blades", "op": "mesh", "vertices": [[0.0837, 0.2153, 0], [0.42, 0, 0], [0, 0, 0], [-0.2153, 0.0837, 0], [0, 0.42, 0],
                                                      [-0.0837, -0.2153, 0], [-0.42, 0, 0], [0.2153, -0.0837, 0], [0, -0.42, 0]],
       "faces": [[0, 1, 2], [3, 4, 2], [5, 6, 2], [7, 8, 2]],
       "face_materials": ["pin_red", "pin_yellow", "pin_blue", "pin_green"],
       "transform": {"rotate": [0, 0, 15], "translate": [-1.85, 5.05, 0]}},
      box("bearing_post", "timber", [0.2, WY + 0.3 - BED, 0.2], [3.3, (WY + 0.3 + BED) / 2, 0], ["bottom"]),
      flume(), fall()]
L1 += wheel(8)
L1 += trestle("trestle_a", 1.6, False)
L1 += trestle("trestle_b", 3.3, False)

# ------------------------------------------------------------------------------- level 2 (from 60 m)
L2 = [box("house", "boards", [HX1 - HX0, PLATE, 2 * HZ], [-0.2, PLATE / 2, 0], ["bottom"]),
      {"id": "roof", "op": "extrude", "depth": 3.6, "material": "thatch", "points": [[-2, 0], [2, 0], [0, 1.8]],
       "transform": {"rotate": [0, 90, 0], "translate": [-0.2, 2.15, 0]}},
      box("flume", "timber", [0.5, 0.25, FL_Z1 - FL_Z0], [WX, FL_Y + 0.125, (FL_Z0 + FL_Z1) / 2], ["bottom", "front", "back"],
          faces={"top": "water"})]
L2 += wheel(band=False)

for nodes in (L0, L1, L2):
    shift(nodes, *SHIFT)

recipe = {
    "format": "mei-asset", "version": 1, "name": "watermill",
    "budget": {"triangles": 500},
    "sheets": {"mill": {"image": "art/mill_sheet.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": L0,
    "lod": {"levels": [{"distance": 24, "nodes": L1}, {"distance": 60, "nodes": L2}], "band": 2},
}

# ------------------------------------------------------------------------------- collision
C = [cuboid("house", -1.85, 1.45, 0, PLATE, -1.55, 1.55),
     # the thatch (42 degrees: the player slides off it)
     solid("roof", [[-2.0, 2.15, -2.0], [1.6, 2.15, -2.0], [1.6, 2.15, 2.0], [-2.0, 2.15, 2.0],
                    [-2.0, 4.25, 0], [1.6, 4.25, 0]],
           [[0, 1, 2, 3], [0, 1, 5, 4], [3, 2, 5, 4], [0, 4, 3], [1, 5, 2]]),
     cuboid("wheel", WX - WW / 2 - 0.05, WX + WW / 2 + 0.05, BED, WY + 2.05, -2.05, 2.05),
     cuboid("bearing_post", 3.2, 3.42, BED, WY + 0.3, -0.12, 0.12),
     # the flume: a 0.5 m beam at 3.0, walkable
     cuboid("flume", WX - 0.25, WX + 0.25, FL_Y, FL_Y + 0.25, FL_Z0, FL_Z1),
     cuboid("trestle_a", WX - 0.4, WX + 0.4, BED + 0.05, FL_Y - 0.02, 1.5, 1.7),
     cuboid("trestle_b", WX - 0.4, WX + 0.4, BED + 0.05, FL_Y - 0.02, 3.2, 3.4),
     cuboid("bales", 0.25, 1.23, 0, 0.85, -2.32, -1.68)]
shift(C, *SHIFT)
col = {"format": "mei-asset", "version": 1, "name": "watermill_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": C}

sx, sz = SHIFT
P = lambda x, y, z: [round(x + sx, 2), y, round(z + sz, 2)]
cams = [
    {"name": "park", "eye": P(-4, 1.6, -9), "target": P(1, 1.6, 0)},
    {"name": "bridge", "eye": P(5.5, 1.2, -6), "target": P(1.5, 1.2, 0.5)},
    {"name": "canal_wading", "eye": P(6.5, WATER + 1.6, 3), "target": P(WX, 0.8, 0)},
    {"name": "lane_across", "eye": P(14, 2.6, -2), "target": P(0, 1.8, 0.5)},
    {"name": "on_flume", "eye": P(WX, FL_Y + 0.25 + 1.6, 3.6), "target": P(WX, 1.5, -2)},
]
with open(os.path.join(HERE, "watermill.asset.json"), "w") as fh:
    json.dump(recipe, fh, indent=1)
with open(os.path.join(HERE, "watermill_col.asset.json"), "w") as fh:
    json.dump(col, fh, indent=1)
with open(os.path.join(HERE, "watermill.cameras.json"), "w") as fh:
    json.dump(cams, fh, indent=1)
print("wrote watermill, watermill_col, watermill.cameras.json")
