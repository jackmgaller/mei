#!/usr/bin/env python3
"""Writes vending_machine.asset.json, vending_machine_col.asset.json and the textures in art/.

The shrine town's vending machine, adapted from the lab model examples/assets/lab/vending_machine
(308 triangles). The lab's textures (window, header, buttons, panel, flap, cup, tanuki sticker,
bin label) are read from the lab's art/ folder and composed here into fewer, larger sheets, so the
body, the bin and the cat take pictures on their faces (`faces`) instead of parts of their own.

Run from anywhere: python3 carts/garden/shrinetown/assets/vending_machine/make_vending_machine.py
Needs Pillow.
"""
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABART = os.path.join(REPO, "examples", "assets", "lab", "vending_machine", "art")

BLUE = (0x2f, 0x7f, 0xc1, 255)
PLATE = (0xee, 0xf0, 0xee, 255)
SEAM = (0xc4, 0xc9, 0xd2, 255)
GREY = (0xd9, 0xdd, 0xe4, 255)
BEZEL = (0x5a, 0x5f, 0x6e, 255)
BINGREY = (0x6c, 0x7a, 0x88, 255)
BINLABELBG = (0x7e, 0x8a, 0x96, 255)


def lab(name):
    return Image.open(os.path.join(LABART, name)).convert("RGBA")


def rect(im, x0, y0, x1, y1, c):
    """Fills x0 <= x < x1, y0 <= y < y1."""
    px = im.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            px[x, y] = c


def save(im, name):
    im.convert("RGB").save(os.path.join(HERE, "art", name))


def draw_art():
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    # Front plate, 39 x 82 texels of 2 cm over the body's 0.78 x 1.64 front: a blue edge round a
    # white plate, a seam under the header and one above the bottom row. The parts stand on it.
    im = Image.new("RGBA", (39, 82), BLUE)
    rect(im, 0, 2, 39, 81, PLATE)
    rect(im, 0, 2, 39, 3, SEAM)
    rect(im, 0, 80, 39, 81, SEAM)
    rect(im, 0, 2, 1, 81, SEAM)
    rect(im, 38, 2, 39, 81, SEAM)
    rect(im, 1, 14, 38, 15, SEAM)   # under the header
    rect(im, 1, 71, 38, 72, SEAM)   # over the bottom row
    save(im, "front.png")

    # Side, 38 x 82 texels of 1.8 cm over 0.68 x 1.64: blue with the tanuki sticker at half size.
    im = Image.new("RGBA", (38, 82), BLUE)
    tan = lab("tanuki.png").resize((16, 24), Image.NEAREST)
    im.paste(tan, (11, 34), tan)
    save(im, "side.png")

    # Window with its bezel: the lab's 56 x 100 window inside a 3-texel border.
    im = Image.new("RGBA", (62, 106), BEZEL)
    im.paste(lab("window.png"), (3, 3))
    save(im, "window.png")

    save(lab("header.png"), "header.png")

    # Bottom left: the lab's buttons over its pickup flap, 56 x 36.
    im = Image.new("RGBA", (56, 36), GREY)
    im.paste(lab("buttons.png"), (0, 0))
    im.paste(lab("flap.png"), (0, 14))
    save(im, "lowleft.png")

    # Right column, 20 x 140: the coin panel, the mascot's head, the cup holder.
    im = Image.new("RGBA", (20, 140), GREY)
    im.paste(lab("panel.png"), (0, 0))
    im.paste(lab("tanuki_head.png"), (0, 73))
    im.paste(lab("cup.png"), (0, 118))
    save(im, "column.png")

    # The recycling bin's front, 40 x 88 of 0.9 cm: grey with the lab's label.
    im = Image.new("RGBA", (40, 88), BINGREY)
    im.paste(lab("bin_label.png"), (0, 20))
    save(im, "bin_front.png")

    # The two lids, 12 x 23 texels of 1.8 cm seen from above (+Z up): blue for cans with its
    # round hole, yellow for bottles with its slot.
    HOLE = (0x1c, 0x1e, 0x28, 255)
    im = Image.new("RGBA", (12, 23), (0x2f, 0x68, 0xc0, 255))
    rect(im, 3, 11, 9, 16, HOLE)
    save(im, "lid_can.png")
    im = Image.new("RGBA", (12, 23), (0xf0, 0xc8, 0x38, 255))
    rect(im, 2, 17, 9, 19, HOLE)
    save(im, "lid_pet.png")

    # The cat's face, 14 x 12: an orange tabby with a white muzzle.
    O, D, W, K, P = ((0xe8, 0xa0, 0x50, 255), (0xc0, 0x6a, 0x28, 255), (0xf6, 0xf0, 0xe4, 255),
                     (0x1a, 0x1a, 0x1a, 255), (0xe8, 0x8a, 0xa0, 255))
    im = Image.new("RGBA", (14, 12), O)
    rect(im, 5, 0, 6, 3, D)
    rect(im, 8, 0, 9, 3, D)
    rect(im, 3, 4, 5, 6, K)
    rect(im, 9, 4, 11, 6, K)
    rect(im, 4, 7, 10, 12, W)
    rect(im, 6, 7, 8, 8, P)
    rect(im, 6, 9, 8, 10, SEAM)
    save(im, "cat_face.png")


def box_mesh(x0, x1, y0, y1, z0, z1):
    v = [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]
    f = [[0, 1, 2, 3], [4, 5, 6, 7], [3, 2, 5, 4], [7, 6, 1, 0], [4, 7, 0, 3], [2, 1, 6, 5]]
    return v, f


def make_col():
    parts = [
        ("body", (-0.41, 0.41, 0.0, 1.77, -0.36, 0.36)),   # machine with its cap
        ("bin", (0.44, 0.88, 0.0, 0.845, -0.34, 0.10)),    # the recycling bin
    ]
    nodes = []
    for name, p in parts:
        v, f = box_mesh(*p)
        nodes.append({"id": name, "op": "mesh", "vertices": v, "faces": f,
                      "face_materials": ["solid"] * len(f)})
    recipe = {
        "format": "mei-asset", "version": 1, "name": "vending_machine_col",
        "materials": {"solid": {"color": "#ffffff", "palette": True}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }
    with open(os.path.join(HERE, "vending_machine_col.asset.json"), "w") as fh:
        json.dump(recipe, fh, indent=1)
        fh.write("\n")


def tex(name, **kw):
    t = {"image": f"art/{name}.png", "bits": 4, "projection": "fit"}
    t.update(kw)
    return t


def make_recipe():
    m = {
        "blue": {"color": "#2f7fc1", "palette": True, "tag": "body"},
        "dark": {"color": "#1c1e28", "palette": True},
        "white": {"color": "#eef0ee", "palette": True},
        "plate": {"color": "#eef0ee", "texture": tex("front")},
        "side": {"color": "#2f7fc1", "texture": tex("side")},
        "window": {"color": "#2a2c38", "class": "emissive", "texture": tex("window")},
        "header": {"color": "#2a5fa8", "class": "emissive", "texture": tex("header")},
        "lowleft": {"color": "#d9dde4", "texture": tex("lowleft")},
        "column": {"color": "#d9dde4", "texture": tex("column")},
        "binbody": {"color": "#6c7a88", "palette": True},
        "binfront": {"color": "#6c7a88", "texture": tex("bin_front")},
        "lidcan": {"color": "#2f68c0", "texture": tex("lid_can")},
        "lidpet": {"color": "#f0c838", "texture": tex("lid_pet")},
        "lidblue": {"color": "#2f68c0", "palette": True},
        "lidyel": {"color": "#f0c838", "palette": True},
        "fur": {"color": "#e8a050", "palette": True},
        "catface": {"color": "#e8a050", "texture": tex("cat_face")},
    }
    n = []

    def add(**k):
        n.append(k)

    def front_part(id_, material, w, h, cx, cy):
        """A thin box standing 3.2 cm proud of the body's front (z -0.34), back to back with it."""
        add(id=id_, op="box", size=[w, h, 0.032], material=material, open=["bottom", "front"],
            transform={"translate": [cx, cy, -0.356]})

    add(id="kick", op="box", size=[0.70, 0.14, 0.60], material="dark", open=["bottom", "top"],
        transform={"translate": [0, 0.07, 0]})
    add(id="body", op="box", size=[0.78, 1.64, 0.68], material="blue", open=["bottom", "top"],
        faces={"back": "plate", "left": "side", "right": "side"},
        transform={"translate": [0, 0.92, 0]})
    add(id="cap", op="box", size=[0.86, 0.05, 0.76], material="white",
        transform={"translate": [0, 1.745, 0]})
    front_part("header", "header", 0.72, 0.216, 0.0, 1.55)
    front_part("window", "window", 0.558, 0.954, -0.11, 0.92)
    front_part("lowleft", "lowleft", 0.504, 0.324, -0.108, 0.268)
    front_part("column", "column", 0.18, 1.26, 0.27, 0.75)
    # The recycling bin beside it, a cat on its lids.
    add(id="bin", op="box", size=[0.36, 0.8, 0.36], material="binbody", open=["bottom", "top"],
        faces={"back": "binfront"}, transform={"translate": [0.66, 0.4, -0.12]})
    add(id="lid_can", op="box", size=[0.22, 0.05, 0.44], material="lidblue", open=["bottom", "right"],
        faces={"top": "lidcan"}, transform={"translate": [0.55, 0.82, -0.12]})
    add(id="lid_pet", op="box", size=[0.22, 0.05, 0.44], material="lidyel", open=["bottom", "left"],
        faces={"top": "lidpet"}, transform={"translate": [0.77, 0.82, -0.12]})
    add(id="cat_body", op="lathe", segments=6, caps=False, material="fur",
        profile=[[0.085, 0.84], [0.105, 0.92], [0.075, 1.01], [0, 1.05]],
        transform={"translate": [0.76, 0, -0.04]})
    add(id="cat_head", op="box", size=[0.14, 0.115, 0.1], material="fur", open=["bottom", "front"],
        faces={"back": "catface"}, transform={"translate": [0.76, 1.095, -0.07]})
    add(id="cat_ears", op="group", modifiers=[{"op": "mirror", "axis": "x", "offset": 0.76}], children=[
        {"id": "ear", "op": "cone", "radius": 0.028, "height": 0.05, "segments": 3, "caps": False,
         "material": "fur", "transform": {"translate": [0.805, 1.18, -0.07]}}])
    add(id="cat_tail", op="cone", radius=0.022, height=0.22, segments=3, caps=False, material="fur",
        transform={"translate": [0.89, 0.95, 0.03], "rotate": [0, 0, -28]})

    # Levels of detail. L1 (from 24 m): the body with its cap, the header, window, the bin and its
    # lids; no kick, no side parts, no cat but a cone. L2 (from 60 m): two boxes and the cap.
    keep = {"body", "cap", "header", "window", "bin", "lid_can", "lid_pet"}
    l1 = [k for k in n if k["id"] in keep]
    l1.append({"id": "cat", "op": "cone", "radius": 0.1, "height": 0.2, "segments": 5, "caps": False,
               "material": "fur", "transform": {"translate": [0.76, 0.945, -0.04]}})
    l2 = [k for k in n if k["id"] in {"body", "cap", "bin"}]
    lod = {"levels": [{"distance": 24, "nodes": l1}, {"distance": 60, "nodes": l2}],
           "cull": 100, "band": 1}

    recipe = {
        "format": "mei-asset", "version": 1, "name": "vending_machine",
        "budget": {"vertices": 200, "triangles": 200},
        "materials": m,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "lod": lod,
        "nodes": n,
    }
    with open(os.path.join(HERE, "vending_machine.asset.json"), "w") as fh:
        json.dump(recipe, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    draw_art()
    make_col()
    make_recipe()
