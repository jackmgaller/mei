#!/usr/bin/env python3
"""Writes phone_booth.asset.json, phone_booth_col.asset.json and the small textures in art/.

The shrine town's phone booth, adapted from the lab model examples/assets/lab/phone_booth (795
triangles). Run from anywhere: python3 carts/garden/shrinetown/assets/phone_booth/make_phone_booth.py

The glass panes' texel grids are read from the lab recipe; sign.png is the lab's. The cat's face,
the phone's front and the shelf top are drawn here (4-bit, a few colours each).
"""
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "phone_booth", "phone_booth.asset.json")


def hexrgb(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


def save(img, name):
    img.save(os.path.join(HERE, "art", name))


def draw_art():
    # Cat face, 16 x 14: a white cat, black eyes, pink nose, a red collar along the bottom.
    W, K, P, R, G = map(hexrgb, ("#f4f0e6", "#242424", "#e88aa0", "#d03a30", "#c8c0b0"))
    im = Image.new("RGB", (16, 14), W)
    px = im.load()
    for x in range(16):
        px[x, 12] = R
        px[x, 13] = R
    for x, y in ((3, 4), (3, 5), (4, 4), (4, 5), (11, 4), (11, 5), (12, 4), (12, 5)):
        px[x, y] = K
    px[7, 7] = px[8, 7] = P
    px[6, 8] = px[9, 8] = G
    px[7, 9] = px[8, 9] = G
    for x in (0, 1, 14, 15):  # whisker hints
        px[x, 7] = G
        px[x, 9] = G
    save(im, "cat_face.png")

    # Phone front, 24 x 28: cream body, a handset cradle on top, a card slot, a green display,
    # a 3 x 4 keypad and a coin slot.
    C, D, B, GR, Y = map(hexrgb, ("#f0e4a8", "#c8b878", "#2a2a2a", "#3f8f5c", "#e8c040"))
    im = Image.new("RGB", (24, 28), C)
    px = im.load()
    for x in range(24):
        px[x, 0] = px[x, 1] = D
        px[x, 27] = D
    for y in range(28):
        px[0, y] = px[23, y] = D
    for y in range(4, 8):  # display
        for x in range(5, 19):
            px[x, y] = GR
    for x in range(6, 18):  # card slot
        px[x, 10] = B
    for r in range(4):  # keypad
        for c in range(3):
            for dy in range(2):
                for dx in range(3):
                    px[5 + c * 5 + dx, 13 + r * 3 + dy] = B if (r, c) != (3, 1) else Y
    for y in range(25, 27):
        for x in range(10, 14):
            px[x, y] = B
    save(im, "phone_front.png")

    # Shelf top, 46 x 15 (the top seen from above, +Z up): a yellow directory on the left.
    S, BK, PG = map(hexrgb, ("#2b7f4e", "#e8c43c", "#b89a2c"))
    im = Image.new("RGB", (46, 15), S)
    px = im.load()
    for y in range(3, 12):
        for x in range(4, 14):
            px[x, y] = BK
    for y in range(3, 12):
        px[4, y] = PG
    for x in range(4, 14):
        px[x, 11] = PG
    save(im, "shelf_top.png")


def box_mesh(x0, x1, y0, y1, z0, z1):
    v = [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]
    f = [[0, 1, 2, 3], [4, 5, 6, 7], [3, 2, 5, 4], [7, 6, 1, 0], [4, 7, 0, 3], [2, 1, 6, 5]]
    return v, f


def make_col():
    parts = [
        (-0.6, 0.6, 0.0, 2.15, -0.6, 0.6),     # the booth, to the top of its eaves
        (-0.28, 0.28, 2.1, 2.6, -0.1, 0.1),   # the sign
        (0.68, 1.04, 0.0, 0.45, -0.18, 0.18),  # the planter
    ]
    nodes = []
    for i, p in enumerate(parts):
        v, f = box_mesh(*p)
        nodes.append({"id": ("body", "sign", "planter")[i], "op": "mesh", "vertices": v, "faces": f,
                      "face_materials": ["solid"] * len(f)})
    recipe = {
        "format": "mei-asset", "version": 1, "name": "phone_booth_col",
        "materials": {"solid": {"color": "#ffffff", "palette": True}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }
    with open(os.path.join(HERE, "phone_booth_col.asset.json"), "w") as fh:
        json.dump(recipe, fh, indent=1)
        fh.write("\n")


def make_recipe():
    lab = json.load(open(LAB))["materials"]
    m = {
        "green": {"color": "#3fae68",
                  "texture": {"pattern": "planks", "colors": ["#3fae68", "#2b7f4e", "#4cbb74"],
                              "params": {"boards": 4, "joint": 1}, "projection": "planar",
                              "axis": "z", "scale": [0.84, 0.84], "rotate": 90}},
        "dark": {"color": "#2b7f4e", "palette": True},
        "concrete": lab["concrete"],
                "glass": lab["glass"],
        "sign": {"color": "#f6f4d6", "class": "emissive",
                 "texture": {"image": "art/sign.png", "bits": 4, "projection": "fit"}},
                "phone": {"color": "#f0e4a8",
                  "texture": {"image": "art/phone_front.png", "bits": 4, "projection": "fit"}},
        "phoneside": {"color": "#d8c888", "palette": True},
        "shelf": {"color": "#2b7f4e",
                  "texture": {"image": "art/shelf_top.png", "bits": 4, "projection": "fit"}},
        "catface": {"color": "#f4f0e6",
                    "texture": {"image": "art/cat_face.png", "bits": 4, "projection": "fit"}},
        "cat": {"color": "#f4f0e6", "palette": True},
        "umb": {"color": "#f0c830", "palette": True},
                "pot": {"color": "#b8704a", "palette": True},
        "bush": {"color": "#3f8f3c", "palette": True},
        "bloom": {"color": "#f08ab0", "palette": True},
    }
    n = []

    def add(**k):
        n.append(k)

    add(id="slab", op="box", size=[1.14, 0.1, 1.14], material="concrete", open=["bottom"],
        transform={"translate": [0, 0.05, 0]})
    # Front posts; the back corners are the back wall's own width and the side walls.
    add(id="posts", op="group", modifiers=[{"op": "mirror", "axis": "x"}], children=[
        {"id": "post", "op": "box", "size": [0.12, 2.0, 0.12], "material": "dark",
         "open": ["bottom", "top"], "transform": {"translate": [0.46, 1.1, -0.46]}}])
    add(id="lowback", op="box", size=[1.04, 2.0, 0.08], material="green", open=["bottom", "top"],
        transform={"translate": [0, 1.1, 0.46]})
    add(id="walls", op="group", modifiers=[{"op": "mirror", "axis": "x"}], children=[
        {"id": "lowside", "op": "box", "size": [0.04, 0.85, 0.88], "material": "green",
         "open": ["bottom", "back", "front", "top"], "transform": {"translate": [0.46, 0.525, 0]}}])
    add(id="sides", op="group", modifiers=[{"op": "mirror", "axis": "x"}], children=[
        {"id": "sidepane", "op": "mesh", "material": "glass",
         "vertices": [[0.46, 0.95, -0.42], [0.46, 2.11, -0.42], [0.46, 2.11, 0.42],
                      [0.46, 0.95, 0.42]], "faces": [[0, 1, 2, 3]]}])
    # The door, open 60 degrees toward the visitor.
    add(id="door", op="group", transform={"pivot": [-0.42, 0, -0.46], "rotate": [0, 60, 0]}, children=[
        {"id": "doorlow", "op": "box", "size": [0.84, 0.85, 0.05], "material": "green",
         "open": ["bottom"], "transform": {"translate": [0, 0.525, -0.46]}},
        {"id": "doorpane", "op": "mesh", "material": "glass",
         "vertices": [[0.42, 0.95, -0.46], [-0.42, 0.95, -0.46], [-0.42, 2.07, -0.46],
                      [0.42, 2.07, -0.46]], "faces": [[0, 1, 2, 3]]}])
    add(id="eaves", op="box", size=[1.2, 0.07, 1.2], material="dark", open=["bottom"],
        transform={"translate": [0, 2.145, 0]})
    add(id="roof", op="lathe", segments=4, caps=False, material="dark",
        profile=[[0.82, 2.18], [0, 2.4]], transform={"rotate": [0, 45, 0]})
    add(id="signbody", op="box", size=[0.56, 0.24, 0.2], material="dark", open=["bottom"],
        faces={"back": "sign", "front": "sign"}, transform={"translate": [0, 2.5, 0]})
    # Inside: the shelf with the directory painted on it, the phone, the cat.
    add(id="shelf", op="box", size=[0.92, 0.04, 0.3], material="dark", open=["bottom", "front", "left", "right"],
        faces={"top": "shelf"}, transform={"translate": [0, 1.1, 0.29]})
    add(id="phonebody", op="box", size=[0.34, 0.4, 0.2], material="phoneside", open=["bottom", "front"],
        faces={"back": "phone"}, transform={"translate": [0, 1.31, 0.33]})
    add(id="catbody", op="lathe", segments=5, caps=False, material="cat",
        profile=[[0.09, 1.12], [0.085, 1.2], [0, 1.27]], transform={"translate": [0.27, 0, 0.31]})
    add(id="cathead", op="box", size=[0.14, 0.11, 0.1], material="cat", open=["bottom", "front"],
        faces={"back": "catface"}, transform={"translate": [0.27, 1.33, 0.3]})
    add(id="catears", op="group", modifiers=[{"op": "mirror", "axis": "x", "offset": 0.27}], children=[
        {"id": "catear", "op": "cone", "radius": 0.032, "height": 0.06, "segments": 3, "caps": False,
         "material": "cat", "transform": {"translate": [0.315, 1.41, 0.3]}}])
    # Outside: the planter, the umbrella left in the corner.
    add(id="pot", op="lathe", segments=5, caps=False, material="pot",
        profile=[[0.12, 0.0], [0.17, 0.26]], transform={"translate": [0.86, 0, 0]})
    add(id="bush", op="lathe", segments=5, caps=False, material="bush",
        profile=[[0.2, 0.26], [0.23, 0.36], [0, 0.5]], transform={"translate": [0.86, 0, 0]})
    add(id="blooms", op="group", children=[
        {"id": "bl0", "op": "cone", "radius": 0.05, "height": 0.07, "segments": 3, "caps": False,
         "material": "bloom", "transform": {"translate": [0.8, 0.42, -0.2]}},
        {"id": "bl1", "op": "cone", "radius": 0.05, "height": 0.07, "segments": 3, "caps": False,
         "material": "bloom", "transform": {"translate": [0.96, 0.37, -0.12]}}])
    add(id="ttstring", op="box", size=[0.012, 0.2, 0.012], material="cat",
        open=["top", "bottom", "left", "right"], transform={"translate": [0.4, 2.0, -0.62]})
    add(id="ttcloth", op="cone", radius=0.06, height=0.14, segments=4, caps=False, material="cat",
        transform={"translate": [0.4, 1.83, -0.62], "rotate": [180, 0, 0]})
    add(id="umbrella", op="cone", radius=0.05, height=0.85, segments=5, caps=False, material="umb",
        transform={"translate": [-0.62, 0.52, 0.12], "rotate": [0, 0, 10]})

    # Levels of detail. L1 (from 24 m): a plain green shell, the roof, the sign and the pot. L2
    # (from 60 m): the shell, the roof and the sign. Culled from 100 m.
    slab = n[0]
    eaves = next(k for k in n if k["id"] == "eaves")
    roof = next(k for k in n if k["id"] == "roof")
    sign = next(k for k in n if k["id"] == "signbody")
    pot = next(k for k in n if k["id"] == "pot")
    shell = {"id": "shell", "op": "box", "size": [1.04, 2.0, 1.04], "material": "green",
             "open": ["bottom"], "transform": {"translate": [0, 1.1, 0]}}
    lod = {"levels": [
        {"distance": 24, "nodes": [slab, shell, eaves, roof, sign, pot]},
        {"distance": 60, "nodes": [dict(shell, size=[1.04, 2.0, 1.04]), roof, sign]},
    ], "cull": 100, "band": 1}

    recipe = {
        "format": "mei-asset", "version": 1, "name": "phone_booth",
        "budget": {"vertices": 200, "triangles": 170},
        "materials": m,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "lod": lod,
        "nodes": n,
    }
    with open(os.path.join(HERE, "phone_booth.asset.json"), "w") as fh:
        json.dump(recipe, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    draw_art()
    make_col()
    make_recipe()
