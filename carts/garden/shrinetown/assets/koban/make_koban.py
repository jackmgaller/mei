#!/usr/bin/env python3
"""Writes the shrine town's koban (police box): art/koban_sheet.png (+ .sheet.json),
koban.asset.json and koban_col.asset.json.

Adapted from the lab model (examples/assets/lab/koban, 823 triangles), whose sheet and roof tile
it reads. Same size (4 x 3 m, 3 m walls), same tiles, blue band, red lamp, 交番 sign, poster
board, mascot poster, bench, police bicycle, stop sign and traffic mirror. The cut: the front
wall's window, door and board and the side wall's mascot poster are painted into the walls'
textures; the bicycle, mirror and antenna are cutout cards; the hip roof is four faces, pitched
at 27.7 degrees so it is walkable (its eave, 3.35 up, is a ledge to grab from the plaza).

Run: python3 carts/garden/shrinetown/assets/koban/make_koban.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "koban")
LAB = os.path.join(LABDIR, "art", "koban_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]
LAB_MATERIALS = json.load(open(os.path.join(LABDIR, "koban.asset.json")))["materials"]

# ---- dimensions (metres) ---------------------------------------------------------------
BW, BD = 4.0, 3.0            # walls
B0, B1 = 0.2, 3.2            # wall bottom (on the plinth) and top
EAVE = 3.35
RIDGE = 4.4                  # 1.05 over 2.0: 27.7 degrees on all four faces
RW, RD = 5.0, 4.0            # eave rectangle
TPM = 16                     # texels a metre on the walls (the lab's tile: 4 a metre, 4 texels)
TILE = ["#e6d9ba", "#c4b89a", "#dccfae"]


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def tiles(w, h):
    """The lab's wall tile drawn out: 4 x 4 texel tiles, one texel of grout, every other one
    the alternate colour (the kit's tile pattern, count 4, grout 1)."""
    img = Image.new("RGBA", (w, h), TILE[1])
    d = ImageDraw.Draw(img)
    for ty in range(0, h, 4):
        for tx in range(0, w, 4):
            c = TILE[0] if ((tx // 4) + (ty // 4)) % 2 == 0 else TILE[2]
            d.rectangle([tx, ty, tx + 2, ty + 2], fill=c)
    return img


def draw_front(src):
    """64 x 48: the front wall (4 x 3 m): window, door, notice board."""
    img = tiles(64, 48)
    d = ImageDraw.Draw(img)
    img.paste(lab(src, "window").resize((18, 18), Image.NEAREST), (9, 18))
    d.rectangle([7, 36, 28, 37], fill="#d9cdb2")                 # sill
    img.paste(lab(src, "door").resize((18, 32), Image.NEAREST), (32, 16))
    img.paste(lab(src, "board").resize((11, 16), Image.NEAREST), (51, 19))
    d.rectangle([50, 17, 62, 18], fill="#d9cdb2")                # board hood
    return img


def draw_side(src):
    """48 x 48: the right wall (3 x 3 m) with the mascot poster."""
    img = tiles(48, 48)
    img.alpha_composite(lab(src, "mascot").resize((16, 16), Image.NEAREST), (19, 15))
    return img


def draw_bike():
    """32 x 20: the police bicycle, white, with its basket; holes around it."""
    img = Image.new("RGBA", (32, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for cx in (6, 25):
        d.ellipse([cx - 6, 7, cx + 6, 19], outline="#1d1d20")
        d.point((cx, 13), fill="#9a9ea4")
    frame = "#f4f1e8"
    d.line([6, 13, 13, 13, 22, 6, 13, 13], fill=frame)
    d.line([12, 5, 13, 13], fill=frame)
    d.line([12, 7, 22, 7], fill=frame)
    d.line([22, 4, 25, 13], fill=frame)
    d.rectangle([10, 3, 14, 4], fill="#1d1d20")
    d.line([20, 3, 24, 3], fill="#9a9ea4")
    d.rectangle([24, 4, 30, 9], fill="#b8bcc0", outline="#8a8e94")
    d.rectangle([3, 3, 9, 6], fill="#2e3b52")                   # the box on the carrier
    return img


def draw_mirror():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, 15, 15], fill="#e8801a")
    d.ellipse([2, 2, 13, 13], fill="#9cc4d6")
    d.line([4, 9, 8, 5], fill="#d8eef6")
    return img


def draw_antenna():
    img = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([0, 4, 15, 4], fill="#33353a")
    for x in (2, 6, 10, 14):
        d.line([x, 0, x, 7], fill="#33353a")
    return img


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (128, 96), (0, 0, 0, 0))
    cells = {}

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("front", draw_front(src), 0, 0)
    put("side", draw_side(src), 64, 0)
    put("sign", lab(src, "sign"), 0, 48)
    put("stop", lab(src, "stop"), 48, 48)
    put("aframe", lab(src, "aframe"), 80, 48)
    put("grille", lab(src, "grille"), 96, 48)
    put("bike", draw_bike(), 0, 64)
    put("mirror", draw_mirror(), 32, 64)
    put("antenna", draw_antenna(), 112, 0)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "koban_sheet.png"))
    with open(os.path.join(HERE, "art", "koban_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v, 4)


def box(id, size, at, material, open=None, faces=None, rotate=None):
    n = {"id": id, "op": "box", "size": [r(s) for s in size], "material": material}
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    t = {}
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n["transform"] = t
    return n


def mesh(id, material, verts, faces, uvs=None):
    n = {"id": id, "op": "mesh", "material": material,
         "vertices": [[r(c) for c in p] for p in verts], "faces": faces}
    if uvs:
        n["uvs"] = uvs
    return n


def cyl(id, radius, height, at, material, segments=6, caps=True):
    n = {"id": id, "op": "cylinder", "radius": radius, "height": r(height), "segments": segments,
         "material": material, "transform": {"translate": [r(a) for a in at]}}
    if not caps:
        n["caps"] = False
    return n


def sheet(cellname, bits=8):
    t = {"sheet": "art", "cell": cellname, "projection": "fit"}
    if bits == 8:
        t["bits"] = 8
    return t


MATERIALS = {
    "concrete": LAB_MATERIALS["concrete"],
    "wall": LAB_MATERIALS["wall"],
    "front": {"color": TILE[0], "tag": "wall", "texture": sheet("front")},
    "side": {"color": TILE[0], "tag": "wall", "texture": sheet("side")},
    "police_blue": {"color": "#2a4a82", "palette": True},
    "fascia": {"color": "#d9cdb2", "palette": True},
    "roof_a": LAB_MATERIALS["roof_a"],
    "roof_b": LAB_MATERIALS["roof_b"],
    "iron": {"color": "#33353a", "palette": True, "double_sided": True},
    "pole": {"color": "#d8d8d4", "palette": True, "double_sided": True},
    "lamp": {"color": "#e8281e", "class": "emissive", "tag": "lantern"},
    "cone": {"color": "#e85a1a", "palette": True},
    "pot": {"color": "#b86a3a", "palette": True},
    "leaf": {"color": "#3c5a34", "palette": True},
    "ac_body": {"color": "#d6d8d4", "palette": True},
    "bench": LAB_MATERIALS["bench"],
    "sign": {"color": "#1d3a6e", "class": "emissive", "tag": "sign", "texture": sheet("sign")},
    "stop": {"color": "#c8201e", "double_sided": True, "texture": sheet("stop")},
    "aframe": {"color": "#f4f1e8", "double_sided": True, "texture": sheet("aframe")},
    "grille": {"color": "#d7d9d6", "texture": sheet("grille", bits=4)},
    "bike": {"color": "#f4f1e8", "double_sided": True, "texture": sheet("bike", bits=4)},
    "mirror": {"color": "#9cc4d6", "double_sided": True, "texture": sheet("mirror", bits=4)},
    "antenna": {"color": "#33353a", "double_sided": True, "texture": sheet("antenna", bits=4)},
}


def roof(eave=EAVE, ridge=RIDGE):
    hx, hz = RW / 2, RD / 2
    v = [[-hx, eave, -hz], [hx, eave, -hz], [hx, eave, hz], [-hx, eave, hz],
         [-0.5, ridge, 0.0], [0.5, ridge, 0.0]]
    return [mesh("roof_front", "roof_a", v, [[0, 4, 5, 1]]),
            mesh("roof_back", "roof_a", v, [[2, 5, 4, 3]]),
            mesh("roof_west", "roof_b", v, [[3, 4, 0]]),
            mesh("roof_east", "roof_b", v, [[1, 5, 2]])]


def walls():
    return box("walls", [BW, B1 - B0, BD], [0, (B0 + B1) / 2, 0], "wall",
               open=["top", "bottom"], faces={"back": "front", "right": "side"})


# ---- level 0 ---------------------------------------------------------------------------
def level0():
    zf = -BD / 2
    n = [box("plinth", [4.3, 0.2, 3.3], [0, 0.1, 0], "concrete", open=["bottom"]),
         walls(),
         box("band", [4.1, 0.25, 3.1], [0, 3.075, 0], "police_blue", open=["top", "bottom"]),
         box("soffit", [RW, 0.15, RD], [0, 3.275, 0], "fascia", open=["top"])]
    n += roof()
    n.append(box("ridge", [1.2, 0.2, 0.24], [0, RIDGE + 0.04, 0], "iron", open=["bottom"]))
    # the sign over the door, standing 8 cm out
    n.append(box("sign", [1.5, 0.5, 0.08], [0.55, 2.62, zf - 0.03], "fascia", open=["front"],
                 faces={"back": "sign"}))
    # the red lamp on its arm over the window
    n.append(mesh("lamp_arm", "iron", [[-0.9, 2.5, zf - 0.45], [-0.9, 2.5, zf + 0.01],
                                       [-0.9, 2.44, zf + 0.01], [-0.9, 2.44, zf - 0.45]],
                  [[0, 1, 2, 3]]))
    n[-1]["material"] = "iron"
    n.append({"id": "lamp", "op": "lathe", "segments": 6, "material": "lamp",
              "profile": [[0.0, -0.24], [0.22, -0.1], [0.22, 0.1], [0.0, 0.26]],
              "transform": {"translate": [-0.9, 2.7, zf - 0.45]}})
    # the antenna mast on the ridge
    n.append(cyl("mast", 0.025, 1.0, [-0.3, RIDGE + 0.5, 0], "iron", segments=3, caps=False))
    n.append(mesh("mast_yagi", "antenna", [[-0.37, RIDGE + 0.95, 0.4], [-0.37, RIDGE + 0.95, -0.4],
                                           [-0.37, RIDGE + 0.55, -0.4], [-0.37, RIDGE + 0.55, 0.4]],
                  [[0, 1, 2, 3]]))
    # the air conditioner on the west wall
    n.append(box("ac", [0.28, 0.5, 0.75], [-BW / 2 - 0.13, 0.95, 0.3], "ac_body",
                 open=["right"], faces={"left": "grille"}))
    # pot and shrub by the door
    n.append(cyl("pot", 0.17, 0.34, [1.75, 0.17, zf - 0.4], "pot", segments=5, caps=False))
    n.append({"id": "shrub", "op": "sphere", "radius": 0.28, "segments": 5, "rings": 3,
              "material": "leaf", "transform": {"scale": [1, 1.15, 1],
                                                "translate": [1.75, 0.58, zf - 0.4]}})
    n.append({"id": "cone", "op": "cone", "radius": 0.13, "height": 0.45, "segments": 6,
              "material": "cone", "transform": {"translate": [1.3, 0.225, zf - 1.25]}})
    # the bench under the mascot poster, on the east wall
    n.append(box("bench_seat", [0.42, 0.06, 1.3], [BW / 2 + 0.23, 0.48, 0.2], "bench",
                 open=["bottom"]))
    n.append(box("bench_back", [0.05, 0.38, 1.3], [BW / 2 + 0.04, 0.76, 0.2], "bench",
                 open=["left", "bottom"]))
    for i, z in enumerate((-0.35, 0.75)):
        n.append(mesh(f"bench_leg_{i}", "iron",
                      [[BW / 2 + 0.05, 0.45, z], [BW / 2 + 0.42, 0.45, z],
                       [BW / 2 + 0.42, 0.0, z], [BW / 2 + 0.05, 0.0, z]], [[0, 1, 2, 3]]))
        n[-1]["material"] = "pole"
    # the stop sign on its pole, front right
    n.append(cyl("stop_pole", 0.035, 2.4, [2.6, 1.2, zf - 0.6], "pole", segments=3, caps=False))
    n.append(mesh("stop_sign", "stop", [[2.6, 1.995, zf - 0.66], [3.05, 2.4, zf - 0.66],
                                        [2.15, 2.4, zf - 0.66]], [[0, 1, 2]],
                  uvs=[[0.5, 1.0], [1.0, 0.0], [0.0, 0.0]]))
    # the A-frame stand board, front left
    n.append(mesh("aframe", "aframe", [[-2.47, 0.9, zf - 0.8], [-3.03, 0.9, zf - 0.8],
                                       [-3.03, 0.0, zf - 1.1], [-2.47, 0.0, zf - 1.1]],
                  [[0, 1, 2, 3]]))
    n.append(mesh("aframe_back", "aframe", [[-3.03, 0.9, zf - 0.76], [-2.47, 0.9, zf - 0.76],
                                            [-2.47, 0.0, zf - 0.46], [-3.03, 0.0, zf - 0.46]],
                  [[0, 1, 2, 3]]))
    # the police bicycle parked by the window
    n.append(mesh("bicycle", "bike", [[-2.15, 1.0, zf - 0.5], [-0.55, 1.0, zf - 0.5],
                                      [-0.55, 0.0, zf - 0.5], [-2.15, 0.0, zf - 0.5]],
                  [[0, 1, 2, 3]]))
    # the traffic mirror on the west side
    n.append(cyl("mirror_pole", 0.04, 2.9, [-3.0, 1.45, 0.9], "pole", segments=3, caps=False))
    n.append(mesh("mirror", "mirror", [[-3.35, 2.9, 0.84], [-2.65, 2.9, 0.84],
                                       [-2.65, 2.2, 0.84], [-3.35, 2.2, 0.84]], [[0, 1, 2, 3]]))
    return n


def level1():
    zf = -BD / 2
    n = [box("plinth", [4.3, 0.2, 3.3], [0, 0.1, 0], "concrete", open=["bottom"]),
         walls(),
         box("soffit", [RW, 0.15, RD], [0, 3.275, 0], "police_blue", open=["top"])]
    n += roof()
    n.append(box("sign", [1.5, 0.5, 0.08], [0.55, 2.62, zf - 0.03], "fascia", open=["front"],
                 faces={"back": "sign"}))
    n.append({"id": "lamp", "op": "lathe", "segments": 4, "material": "lamp",
              "profile": [[0.0, -0.24], [0.24, 0.0], [0.0, 0.26]],
              "transform": {"translate": [-0.9, 2.7, zf - 0.45]}})
    return n


def level2():
    return [box("walls", [BW, B1, BD], [0, B1 / 2, 0], "wall", open=["bottom", "top"],
                faces={"back": "front", "right": "side"})] + roof(eave=B1, ridge=RIDGE - 0.15)


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "koban",
        "budget": {"triangles": 200},
        "sheets": {"art": {"image": "art/koban_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 150, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               "solid", open=open)


def collision():
    hx, hz = RW / 2, RD / 2
    ridge = RIDGE
    v = [[-hx, EAVE, -hz], [hx, EAVE, -hz], [hx, EAVE, hz], [-hx, EAVE, hz],
         [-0.5, ridge, 0.0], [0.5, ridge, 0.0]]
    n = [solid("plinth", -2.15, 2.15, 0, 0.2, -1.65, 1.65, open=["bottom"]),
         solid("walls", -BW / 2, BW / 2, 0.2, 3.2, -BD / 2, BD / 2, open=["bottom", "top"]),
         # the eave: 0.5 m out all round, 3.2-3.35, a ledge to grab
         solid("eave", -hx, hx, 3.2, EAVE, -hz, hz, open=["top"]),
         {"id": "roof", "op": "mesh", "material": "solid", "vertices": v,
          "faces": [[0, 4, 5, 1], [2, 5, 4, 3], [3, 4, 0], [1, 5, 2]]},
         solid("bench", BW / 2 + 0.02, BW / 2 + 0.44, 0, 0.51, -0.45, 0.85, open=["bottom"])]
    return {
        "format": "mei-asset", "version": 1, "name": "koban_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": {"solid": {"color": "#c8c4b8"}},
        "nodes": n,
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("koban.asset.json", recipe())
    write("koban_col.asset.json", collision())
