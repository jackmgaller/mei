"""Writes signal_gantry.asset.json and signal_gantry_col.asset.json beside this script.
Run after changing it: python3 carts/garden/shrinetown/assets/signal_gantry/make_gantry.py

A low signal gantry across viaduct_span_16 at each of the line's ends in the level, where a
rider on a train's roof is swept off. The origin is the viaduct's centre line at the deck (the
world's 9.0); the tracks run along X at z = +-2.0 as on the standard span.

Two galvanised H-columns stand on the cable-trough walkways (z = +-5.3, 0.3 square), carrying a
lattice girder across both tracks whose underside is 4.15 over the rail: 0.51 above
train_emu_car's walkable roof (3.64) and clear of its air conditioner (4.0) and folded
pantograph (3.98). A rider standing on the roof meets the girder's face at the shins and is
swept off the back of the car, unless they hop up onto the grating walkway on top (4.45, 0.81
above the roof). The walkway's handrails (1.0) leave a gap over each track (|z| 0.5..3.5), so
the hop lands. A ladder up the north column (z +5.3, its -X face, 0.2..4.15) is a pole for the
world's `pole` entity. One signal head over each track, each facing the trains that run on it
(left-hand running: the -X face over z = -2, the +X face over z = +2).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

COL_Z = 5.3
UNDER, TOP = 4.15, 4.45
HALF_Z = 5.65
DEPTH = 1.2
RAIL_H = 1.0
RAIL_SEGS = [(-5.6, -3.5), (-0.5, 0.5), (3.5, 5.6)]


def r(v):
    return round(v + 0.0, 4) + 0.0


def fit(cell):
    return {"sheet": "gantry", "cell": cell, "projection": "fit"}


MATERIALS = {
    "steel": {"color": "#9ba3ac", "palette": True},
    "steel_dark": {"color": "#5e6a72", "palette": True},
    "black": {"color": "#2c2a28", "palette": True},
    "truss": {"color": "#4e555c", "texture": fit("truss")},
    "grating": {"color": "#7a828a", "tag": "floor", "texture": fit("grating")},
    "rail": {"color": "#c0c6cc", "double_sided": True, "texture": fit("rail")},
    "ladder": {"color": "#c0c6cc", "double_sided": True, "texture": fit("ladder")},
    "signal": {"color": "#2c2a28", "texture": fit("signal")},
    "green_lamp": {"color": "#3be06a", "class": "emissive", "tag": "lamp"},
}


def box(id_, size, at, material, open_=None, faces=None, decals=None):
    n = {"id": id_, "op": "box", "size": [r(v) for v in size], "material": material,
         "transform": {"translate": [r(v) for v in at]}}
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    return n


def quad(id_, material, corners):
    return {"id": id_, "op": "mesh", "material": material,
            "vertices": [[r(c) for c in p] for p in corners], "faces": [[0, 1, 2, 3]]}


def girder():
    return box("girder", [DEPTH, TOP - UNDER, 2 * HALF_Z], [0, (UNDER + TOP) / 2, 0], "steel",
               faces={"top": "grating", "left": "truss", "right": "truss",
                      "bottom": "steel_dark"})


def columns(plates=True):
    kids = [box("column", [0.3, UNDER + 0.05, 0.3], [0, (UNDER + 0.05) / 2, COL_Z], "steel",
                open_=["top", "bottom"])]
    if plates:
        kids.append(box("plate", [0.6, 0.06, 0.6], [0, 0.03, COL_Z], "steel_dark",
                        open_=["bottom"]))
    return {"id": "columns", "op": "group", "children": kids,
            "modifiers": [{"op": "mirror", "axis": "z"}]}


def rails():
    kids = []
    for k, (z0, z1) in enumerate(RAIL_SEGS):
        for side, x in (("w", -DEPTH / 2 + 0.02), ("e", DEPTH / 2 - 0.02)):
            kids.append(quad(f"rail_{side}{k}", "rail",
                             [[x, TOP + RAIL_H, z0], [x, TOP + RAIL_H, z1], [x, TOP, z1],
                              [x, TOP, z0]]))
    return {"id": "rails", "op": "group", "children": kids}


def ladder():
    x = -0.17
    return quad("ladder", "ladder", [[x, UNDER, COL_Z - 0.225], [x, UNDER, COL_Z + 0.225],
                                     [x, 0.2, COL_Z + 0.225], [x, 0.2, COL_Z - 0.225]])


def signals(level=0):
    out = []
    for k, (x, z, face) in enumerate(((-0.72, -2.0, "left"), (0.72, 2.0, "right"))):
        decals = None
        if level == 0:
            decals = [{"id": "lit", "face": face, "material": "green_lamp", "size": [0.15, 0.16],
                       "at": [0, -0.27]}]
        out.append(box(f"signal_{k}", [0.25, 0.9, 0.35], [x, 4.65, z], "black",
                       faces={face: "signal"}, decals=decals))
    return out


def recipe():
    lod1 = [girder(), columns(False)] + signals(1)
    lod2 = [box("girder", [DEPTH, TOP - UNDER, 2 * HALF_Z], [0, (UNDER + TOP) / 2, 0], "steel",
                open_=["top", "left", "right"]),
            {"id": "columns", "op": "group", "children": [
                box("column", [0.3, UNDER + 0.05, 0.3], [0, (UNDER + 0.05) / 2, COL_Z], "steel",
                    open_=["top", "bottom", "front", "back"])],
             "modifiers": [{"op": "mirror", "axis": "z"}]}]
    return {
        "format": "mei-asset", "version": 1, "name": "signal_gantry",
        "budget": {"triangles": 150},
        "sheets": {"gantry": {"image": "art/gantry.png"}},
        "materials": MATERIALS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": [girder(), columns(), rails(), ladder()] + signals(0),
        "lod": {"levels": [{"distance": 40, "nodes": lod1}, {"distance": 100, "nodes": lod2}],
                "cull": 200, "band": 2},
    }


def collision():
    nodes = [
        box("girder", [DEPTH, TOP - UNDER, 2 * HALF_Z], [0, (UNDER + TOP) / 2, 0], "solid"),
        {"id": "columns", "op": "group", "children": [
            box("column", [0.3, UNDER + 0.05, 0.3], [0, (UNDER + 0.05) / 2, COL_Z], "solid",
                open_=["top", "bottom"])],
         "modifiers": [{"op": "mirror", "axis": "z"}]},
        box("signal_0", [0.25, 0.9, 0.35], [-0.72, 4.65, -2.0], "solid"),
        box("signal_1", [0.25, 0.9, 0.35], [0.72, 4.65, 2.0], "solid"),
    ]
    for k, (z0, z1) in enumerate(RAIL_SEGS):
        for side, sx in (("w", -1), ("e", 1)):
            nodes.append(box(f"rail_{side}{k}", [0.2, RAIL_H, z1 - z0],
                             [sx * (DEPTH / 2 - 0.1), TOP + RAIL_H / 2, (z0 + z1) / 2], "solid",
                             open_=["bottom"]))
    return {"format": "mei-asset", "version": 1, "name": "signal_gantry_col",
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": {"mode": "vertical", "ambient": 0.5},
            "verification": {"required": True, "depth": True, "perspective": True},
            "nodes": nodes}


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("wrote", name)


if __name__ == "__main__":
    write("signal_gantry.asset.json", recipe())
    write("signal_gantry_col.asset.json", collision())
