"""Writes train_emu_car.asset.json and train_emu_car_col.asset.json beside this script.
Run after changing it: python3 carts/garden/shrinetown/assets/train_emu_car/make_train.py

One car of shrine town's two-car local train: a 1990s stainless EMU, 20 m over the couplers,
2.9 m wide, three double-leaf doors a side, a cab at +X and the gangway at -X (the second car is
the same recipe turned 180 degrees, so the set has a cab at each end). Livery and the line's
orange in art/livery.png (art/draw_livery.py).

The origin is the middle of the car at rail level (the viaduct's deck, 9.0 in the world). The
car body runs y 1.0..3.64 (floor 1.15 inside, the platform's edge 1.0); its roof is flat at 3.64
between two chamfers and walkable; the air conditioner on it reaches 4.0 and the folded
pantograph 3.98, so a signal gantry's underside at 4.15 clears everything and sweeps a rider
standing on the roof off it. The windows' glass is the livery's at every level. (Until the alpha,
level 0 laid emissive glass over the windows, pale where the texture's is dark, so the car changed
colour at its first level switch; the glass cost 216 of level 0's 454 triangles.) Level 0 lays
the cab's destination and headlights over the livery as emissive decals (the cart brightens them
at night).

Levels (the shrine town sets the distances in its world, place/station.py): 0 whole; 1 the body,
bogies, equipment, gangway, air conditioner and a pantograph block (80 triangles); 2 the body
alone. `train_emu_pair` is two cars at level 1 as an asset of its own, with
`train_emu_pair_col`: the last train, a mover (an entity draws its mesh's level 0 only).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HALF_L = 9.75                  # body ends
HALF_W = 1.45
BODY_Y0, SIDE_TOP, ROOF = 1.0, 3.45, 3.64
CHAMFER_W = 1.25
COUPLER = 10.0                 # over the couplers: 20 m
BOGIE_X = 6.9


def r(v):
    return round(v + 0.0, 4) + 0.0


def fit(cell, **kw):
    t = {"sheet": "livery", "cell": cell, "projection": "fit"}
    t.update(kw)
    return t


MATERIALS = {
    "side_l": {"color": "#bcc2c6", "texture": fit("side")},
    "side_r": {"color": "#bcc2c6", "texture": fit("side", flip="u")},
    "cab": {"color": "#bcc2c6", "texture": fit("cab")},
    "end": {"color": "#bcc2c6", "texture": fit("end")},
    "bogie": {"color": "#3a3c40", "texture": fit("bogie")},
    "ac": {"color": "#a8aeb2", "texture": fit("ac")},
    "under_side": {"color": "#4a4d52", "texture": fit("under")},
    "roof": {"color": "#8e9498", "palette": True, "tag": "roof"},
    "steel": {"color": "#bcc2c6", "palette": True},
    "dark": {"color": "#2c2e32", "palette": True},
    "rubber": {"color": "#1c1d20", "palette": True},
    "insulator": {"color": "#e8e4dc", "palette": True},
    "orange": {"color": "#e8782a", "palette": True},
    "destination": {"color": "#f2f2ec", "class": "emissive", "tag": "sign"},
    "headlight": {"color": "#fff6d8", "class": "emissive", "tag": "lamp"},
}

PROFILE = [(HALF_W, BODY_Y0), (HALF_W, SIDE_TOP), (CHAMFER_W, ROOF), (-CHAMFER_W, ROOF),
           (-HALF_W, SIDE_TOP), (-HALF_W, BODY_Y0)]
EDGE_MATS = ["side_r", "roof", "roof", "roof", "side_l", "dark"]


def orient(verts, faces):
    c = [sum(p[j] for p in verts) / len(verts) for j in range(3)]
    out = []
    for f in faces:
        a, b, d = verts[f[0]], verts[f[1]], verts[f[2]]
        e1 = [b[j] - a[j] for j in range(3)]
        e2 = [d[j] - a[j] for j in range(3)]
        n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
             e1[0] * e2[1] - e1[1] * e2[0]]
        fc = [sum(verts[i][j] for i in f) / len(f) for j in range(3)]
        out.append(f if sum(n[j] * (fc[j] - c[j]) for j in range(3)) > 0 else f[::-1])
    return out


def body(level=0):
    rear = [[-HALF_L, y, z] for z, y in PROFILE]
    front = [[HALF_L, y, z] for z, y in PROFILE]
    verts = rear + front
    n = len(PROFILE)
    faces, mats = [], []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
        mats.append(EDGE_MATS[i])
    faces.append(list(range(n)))
    mats.append("end")
    faces.append(list(range(n, 2 * n)))
    mats.append("cab")
    faces = orient(verts, faces)
    node = {"id": "body", "op": "mesh", "material": "steel",
            "vertices": [[r(c) for c in v] for v in verts], "faces": faces,
            "face_materials": mats}
    if level == 0:
        # the cab front (x = +9.75, seen from +x): symmetric about z = 0, so either way round.
        # No glass over the windows or the windscreens: the livery's is drawn at every level.
        cab = n + 1
        decals = [
            {"id": "destination", "face": cab, "material": "destination", "size": [2.2, 0.16],
             "at": [0.0, 3.35]},
            {"id": "head_a", "face": cab, "material": "headlight", "size": [0.26, 0.2],
             "at": [-1.085, 1.33]},
            {"id": "head_b", "face": cab, "material": "headlight", "size": [0.26, 0.2],
             "at": [1.085, 1.33]},
        ]
        node["decals"] = decals
    return node


def box(id_, size, at, material, open_=None, faces=None, rotate=None):
    n = {"id": id_, "op": "box", "size": [r(v) for v in size], "material": material,
         "transform": {"translate": [r(v) for v in at]}}
    if rotate:
        n["transform"]["rotate"] = rotate
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    return n


def running_gear(level=0):
    kids = [box("bogie", [2.6, 0.85, 2.0], [BOGIE_X, 0.525, 0], "dark", open_=["top"],
                faces={"back": "bogie", "front": "bogie"})]
    bogies = {"id": "bogies", "op": "group", "children": kids,
              "modifiers": [{"op": "mirror", "axis": "x"}]}
    out = [bogies,
           box("equipment_a", [4.4, 0.57, 2.2], [-2.6, 0.735, 0], "dark", open_=["top"],
               faces={"back": "under_side", "front": "under_side"})]
    if level == 0:
        out.append(box("equipment_b", [3.0, 0.47, 2.0], [2.9, 0.785, 0], "dark", open_=["top"],
                       faces={"back": "under_side", "front": "under_side"}))
    return out


def ends(level=0):
    out = []
    if level == 0:
        out += [
            {"id": "skirt", "op": "extrude", "material": "dark", "depth": 0.15,
             "points": [[-1.2, 1.02], [1.2, 1.02], [0.95, 0.28], [-0.95, 0.28]],
             "transform": {"rotate": [0, 90, 0], "translate": [9.82, 0, 0]}},
            box("coupler_cab", [0.32, 0.2, 0.26], [HALF_L + 0.09, 0.82, 0], "dark",
                open_=["left"]),
            box("coupler_rear", [0.32, 0.2, 0.26], [-HALF_L - 0.09, 0.82, 0], "dark",
                open_=["right"]),
        ]
    out.append(box("gangway", [0.25, 2.1, 1.1], [-HALF_L - 0.12, 2.15, 0], "rubber",
                   open_=["right"]))
    return out


def roof_gear(level=0):
    out = [box("aircon", [2.4, 0.38, 1.9], [-0.6, ROOF - 0.02 + 0.19, 0], "steel",
               open_=["bottom"], faces={"top": "ac"})]
    if level > 0:
        out.append(box("pantograph", [1.6, 0.3, 1.5], [4.6, ROOF + 0.13, 0], "dark",
                       open_=["bottom"]))
        return out
    out += [
        {"id": "gutters", "op": "group", "children": [
            box("gutter", [2 * HALF_L - 0.1, 0.05, 0.06], [0, SIDE_TOP + 0.01, HALF_W + 0.02],
                "steel", open_=["left", "right"])],
         "modifiers": [{"op": "mirror", "axis": "z"}]},
        {"id": "vents", "op": "group", "children": [
            box("vent", [0.5, 0.13, 0.55], [-6.4, ROOF + 0.045, 0], "steel", open_=["bottom"])],
         "modifiers": [{"op": "array", "count": 2, "step": [3.6, 0, 0]}]},
        box("vent_c", [0.5, 0.13, 0.55], [7.6, ROOF + 0.045, 0], "steel", open_=["bottom"]),
    ]
    # a folded single-arm pantograph over the second door bay: insulators, base, two arms,
    # the collector head across the car
    px = 4.6
    out += [
        {"id": "insulators", "op": "group", "children": [
            box("insulator", [0.14, 0.2, 0.14], [px - 0.6, ROOF + 0.08, 0.45], "insulator",
                open_=["bottom", "top"])],
         "modifiers": [{"op": "mirror", "axis": "z"}, {"op": "mirror", "axis": "x",
                                                         "offset": px}]},
        box("panto_base", [1.5, 0.06, 1.2], [px, ROOF + 0.2, 0], "dark"),
        box("panto_lower", [1.3, 0.06, 0.08], [px - 0.1, ROOF + 0.3, 0], "dark",
            rotate=[0, 0, 7]),
        box("panto_upper", [1.4, 0.05, 0.06], [px + 0.1, ROOF + 0.27, 0.12], "dark",
            rotate=[0, 0, -5]),
        box("panto_head", [0.2, 0.06, 1.7], [px + 0.75, ROOF + 0.31, 0], "steel"),
    ]
    return out


def level_nodes(level):
    if level == 2:
        return [body(2)]
    return [body(level)] + running_gear(level) + ends(level) + roof_gear(level)


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "train_emu_car",
        "budget": {"vertices": 1400, "triangles": 1200},
        "sheets": {"livery": {"image": "art/livery.png"}},
        "materials": MATERIALS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": level_nodes(0),
        "lod": {"levels": [{"distance": 40, "nodes": level_nodes(1)},
                           {"distance": 100, "nodes": level_nodes(2)}], "band": 2},
    }


def collision():
    """The body as one block (its underside 0.3 over the rail, so nothing walks under it), the
    air conditioner on the roof."""
    return {"format": "mei-asset", "version": 1, "name": "train_emu_car_col",
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": {"mode": "vertical", "ambient": 0.5},
            "verification": {"required": True, "depth": True, "perspective": True},
            "nodes": [
                box("body", [2 * HALF_L, ROOF - 0.3, 2 * HALF_W], [0, (ROOF + 0.3) / 2, 0],
                    "solid"),
                box("aircon", [2.4, 0.4, 1.9], [-0.6, ROOF - 0.02 + 0.2, 0], "solid",
                    open_=["bottom"]),
            ]}


def pair_collision():
    """The pair's: one block over both bodies and the gangways between them, the two air
    conditioners."""
    return {"format": "mei-asset", "version": 1, "name": "train_emu_pair_col",
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": {"mode": "vertical", "ambient": 0.5},
            "verification": {"required": True, "depth": True, "perspective": True},
            "nodes": [
                box("body", [2 * (COUPLER + HALF_L), ROOF - 0.3, 2 * HALF_W],
                    [0, (ROOF + 0.3) / 2, 0], "solid"),
                box("aircon_e", [2.4, 0.4, 1.9], [COUPLER - 0.6, ROOF - 0.02 + 0.2, 0], "solid",
                    open_=["bottom"]),
                box("aircon_w", [2.4, 0.4, 1.9], [-COUPLER + 0.6, ROOF - 0.02 + 0.2, 0], "solid",
                    open_=["bottom"]),
            ]}


def dump(obj, ind=0):
    sp = '  ' * ind
    if isinstance(obj, dict):
        items = [f'{sp}  {json.dumps(k)}: {dump(v, ind + 1).lstrip()}' for k, v in obj.items()]
        return sp + '{\n' + ',\n'.join(items) + '\n' + sp + '}'
    if isinstance(obj, list):
        flat = json.dumps(obj, separators=(', ', ': '))
        if len(flat) < 92 and not any(isinstance(v, dict) for v in obj):
            return sp + flat
        if all(not isinstance(v, dict) for v in obj):
            return sp + '[\n' + ',\n'.join(sp + '  ' + json.dumps(v, separators=(', ', ': '))
                                           for v in obj) + '\n' + sp + ']'
        return sp + '[\n' + ',\n'.join(dump(v, ind + 1) for v in obj) + '\n' + sp + ']'
    return sp + json.dumps(obj)


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(dump(data) + "\n")
    print("wrote", name)


def pair():
    """The last train (the shrine town's ★5 mover, game.py RACE_TRAIN): two cars at level 1
    (an entity's mesh has no levels), the east one's cab at +X, the west one turned; the origin
    the middle of the set at rail level, the couplers meeting at x 0."""
    out = recipe()
    out["name"] = "train_emu_pair"
    out["budget"] = {"vertices": 300, "triangles": 200}
    out["nodes"] = [
        {"id": "car_e", "op": "group", "children": level_nodes(1),
         "transform": {"translate": [COUPLER, 0, 0]}},
        {"id": "car_w", "op": "group", "children": level_nodes(1),
         "transform": {"rotate": [0, 180, 0], "translate": [-COUPLER, 0, 0]}},
    ]
    del out["lod"]
    used = set()
    stack = list(out["nodes"])
    while stack:
        n = stack.pop()
        used.add(n.get("material"))
        used.update(n.get("face_materials", []))
        if isinstance(n.get("faces"), dict):
            used.update(n["faces"].values())
        stack += n.get("children", [])
    out["materials"] = {k: v for k, v in MATERIALS.items() if k in used}
    return out


if __name__ == "__main__":
    write("train_emu_car.asset.json", recipe())
    write("train_emu_pair.asset.json", pair())
    write("train_emu_pair_col.asset.json", pair_collision())
    write("train_emu_car_col.asset.json", collision())
