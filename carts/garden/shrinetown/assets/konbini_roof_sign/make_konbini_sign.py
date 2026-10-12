#!/usr/bin/env python3
"""Writes konbini_roof_sign.asset.json and konbini_roof_sign_col.asset.json beside this script.
Run after changing it: python3 carts/garden/shrinetown/assets/konbini_roof_sign/make_konbini_sign.py

The konbini's roof sign (until the alpha a grey-box block): a lightbox 5.6 x 1.4 x 0.8 m with
the konbini's logo on both faces (the shrine's street sheet, cell kon_sign, the same picture as
the shop's own sign, so the town's texture set holds it once), on two posts on the roof's deck.
The origin is the middle of its foot on the deck (world (196, 4.7, 30) in the shrine town, the
long faces to the north and south). Red coin 5 sits on its top, 2.3 m over the deck: the
collision is the grey box's block (x +-3, y 0..2.3, z +-0.4), solid down to the deck so nothing
is caught under the box.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HALF_X, HALF_Z = 2.8, 0.4
FOOT, BOX_Y0, TOP = 0.0, 0.9, 2.3
POST_X, POST = 2.2, 0.12

MATERIALS = {
    "sign": {"color": "#fbfaf4", "class": "emissive", "tag": "sign",
             "texture": {"sheet": "street", "cell": "kon_sign", "projection": "fit"}},
    "frame": {"color": "#6a665e", "palette": True},
    "cap": {"color": "#c8c4b8", "palette": True},
}


def box(id_, size, at, material, open_=None, faces=None):
    n = {"id": id_, "op": "box", "size": size, "material": material,
         "transform": {"translate": at}}
    if open_:
        n["open"] = open_
    if faces:
        n["faces"] = faces
    return n


def recipe():
    h = TOP - BOX_Y0
    return {
        "format": "mei-asset", "version": 1, "name": "konbini_roof_sign",
        "budget": {"vertices": 64, "triangles": 40},
        "sheets": {"street": {"image": "../../../shrine/assets/art/street_sheet.png"}},
        "materials": MATERIALS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": [
            box("lightbox", [2 * HALF_X, h, 2 * HALF_Z], [0, BOX_Y0 + h / 2, 0], "frame",
                faces={"front": "sign", "back": "sign", "top": "cap"}),
            {"id": "posts", "op": "group", "children": [
                box("post", [POST, BOX_Y0 + 0.02, POST], [POST_X, (BOX_Y0 + 0.02) / 2, 0], "frame",
                    open_=["top", "bottom"])],
             "modifiers": [{"op": "mirror", "axis": "x"}]},
        ],
        "lod": {"cull": 140},
    }


def collision():
    return {
        "format": "mei-asset", "version": 1, "name": "konbini_roof_sign_col",
        "materials": {"solid": {"color": "#ffffff", "palette": True}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": [box("block", [6.0, TOP, 2 * HALF_Z], [0, TOP / 2, 0], "solid", open_=["bottom"])],
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("wrote", name)


if __name__ == "__main__":
    write("konbini_roof_sign.asset.json", recipe())
    write("konbini_roof_sign_col.asset.json", collision())
