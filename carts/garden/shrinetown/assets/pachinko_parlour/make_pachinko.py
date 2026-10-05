#!/usr/bin/env python3
"""Writes the shrine town's pachinko parlour: art/parlour_sheet.png (+ .sheet.json),
pachinko_parlour.asset.json and pachinko_parlour_col.asset.json.

Adapted from the lab model (examples/assets/lab/pachinko_parlour, 876 triangles, 8.4 x 6.4 m),
whose sheet it reads for the sign, blade sign, banner, doors, machines, vending machine, mascot's
face and windows. The town's parlour is wider (11 m frontage, 9 m deep) to hold the plaza's west
side, with the same two storeys, blue tiles, salmon stucco and the steel-ball mascot on the roof
(its antenna is the 9.1 m of spec 3.1). The doors and machine windows are one shopfront decal and
the side windows a texture, instead of a quad each.

Run: python3 carts/garden/shrinetown/assets/pachinko_parlour/make_pachinko.py   (needs Pillow)
"""
import json
import os
import random

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "pachinko_parlour", "art",
                   "parlour_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]

# ---- dimensions (metres) ---------------------------------------------------------------
W, D = 11.0, 9.0            # ground floor
G = 3.4                     # ground floor height
CORN = 0.25                 # cornice
INSET = 0.2                 # the upper floor stands this far inside the cornice's edge
UW, UD = W - 2 * INSET, D - 2 * INSET
U0 = G + CORN               # 3.65
ROOF = 6.8
PARA = 0.35
TOP = ROOF + PARA           # 7.15
ZF = -D / 2                 # ground floor's front
UZF = -UD / 2               # upper floor's front
STUCCO = ["#f1dcc8", "#e2c4a8"]


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def speckle(img, box, colors, density, seed):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=colors[0])
    for y in range(y0, y1):
        for x in range(x0, x1):
            if rnd.random() < density:
                d.point((x, y), fill=colors[1 + rnd.randrange(len(colors) - 1)])


def draw_storefront(src):
    """160 x 44 for 9.4 x 2.6 m: two machine windows either side of the glass doors."""
    img = Image.new("RGBA", (160, 44), "#2b2832")
    d = ImageDraw.Draw(img)
    door = lab(src, "door").resize((19, 38), Image.NEAREST)
    img.paste(door, (60, 5))
    img.paste(door, (81, 5))
    d.rectangle([58, 3, 101, 4], fill="#8e1f2c")
    machine = lab(src, "machine").resize((16, 24), Image.NEAREST)
    for x0 in (4, 106):
        d.rectangle([x0, 8, x0 + 49, 36], fill="#1c1a22")
        for k in range(3):
            img.paste(machine, (x0 + 1 + 17 * k, 10))
        d.rectangle([x0, 37, x0 + 49, 39], fill="#8a929e")
    return img


def draw_upper_side(src):
    """64 x 28 for the upper floor's side wall (8.6 x 3.5 m): stucco and three windows."""
    img = Image.new("RGBA", (64, 28))
    speckle(img, (0, 0, 64, 28), STUCCO, 0.15, 11)
    win = lab(src, "window").resize((9, 8), Image.NEAREST)
    for x in (10, 28, 46):
        img.paste(win, (x, 9))
    return img


def draw_side_door():
    img = Image.new("RGBA", (8, 16), "#2b2832")
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, 6, 15], fill="#4a4652")
    d.point((5, 8), fill="#c3ccd8")
    return img


def draw_hut_door():
    img = Image.new("RGBA", (8, 12), "#cfd4da")
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 5, 11], fill="#2b2832")
    return img


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (256, 128), (0, 0, 0, 0))
    cells = {}

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        cells[name] = [x, y, im.size[0], im.size[1]]

    put("sign", lab(src, "sign"), 0, 0)
    put("blade", lab(src, "blade"), 128, 0)
    put("banner", lab(src, "banner"), 152, 0)
    put("vend", lab(src, "vend"), 168, 0)
    put("face", lab(src, "face"), 184, 0)
    put("side_door", draw_side_door(), 216, 0)
    put("hut_door", draw_hut_door(), 224, 0)
    put("bulbs_a", lab(src, "bulbs_a"), 0, 32)
    put("bulbs_b", lab(src, "bulbs_b"), 64, 32)
    put("storefront", draw_storefront(src), 0, 40)
    put("upper_side", draw_upper_side(src), 160, 40)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "parlour_sheet.png"))
    with open(os.path.join(HERE, "art", "parlour_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v, 4)


def box(id, size, at, material, open=None, faces=None, decals=None, rotate=None, scale=None):
    n = {"id": id, "op": "box", "size": [r(s) for s in size], "material": material}
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    t = {}
    if scale:
        t["scale"] = scale
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n["transform"] = t
    return n


def quad(id, material, pts):
    return {"id": id, "op": "mesh", "material": material,
            "vertices": [[r(c) for c in p] for p in pts], "faces": [[0, 1, 2, 3]]}


def zquad(id, material, x0, x1, y0, y1, z, facing=-1):
    if facing < 0:
        pts = [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]]
    else:
        pts = [[x1, y1, z], [x0, y1, z], [x0, y0, z], [x1, y0, z]]
    return quad(id, material, pts)


def xquad(id, material, z0, z1, y0, y1, x, facing=1):
    if facing > 0:
        pts = [[x, y1, z0], [x, y1, z1], [x, y0, z1], [x, y0, z0]]
    else:
        pts = [[x, y1, z1], [x, y1, z0], [x, y0, z0], [x, y0, z1]]
    return quad(id, material, pts)


def yquad(id, material, x0, x1, z0, z1, y, up=True):
    if up:
        pts = [[x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0]]
    else:
        pts = [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]
    return quad(id, material, pts)


def cyl(id, radius, height, at, material, segments=6, caps=True):
    n = {"id": id, "op": "cylinder", "radius": radius, "height": r(height), "segments": segments,
         "material": material, "transform": {"translate": [r(a) for a in at]}}
    if not caps:
        n["caps"] = False
    return n


def sphere(id, radius, at, material, segments, rings, scale=None):
    t = {"translate": [r(a) for a in at]}
    if scale:
        t = {"scale": scale, "translate": t["translate"]}
    return {"id": id, "op": "sphere", "radius": radius, "segments": segments, "rings": rings,
            "material": material, "transform": t}


def sheet(cellname, **extra):
    t = {"sheet": "art", "cell": cellname, "projection": "fit"}
    t.update(extra)
    return t


MATERIALS = {
    "tile": {"color": "#3f78a8", "tag": "wall", "texture": {
        "pattern": "tile", "colors": ["#3f78a8", "#e8f0f4", "#5a94c4"],
        "params": {"count": 4, "grout": 1}, "projection": "box", "scale": [1.0, 1.0]}},
    "stucco": {"color": STUCCO[0], "tag": "wall", "texture": {
        "pattern": "speckle", "colors": STUCCO, "params": {"density": 0.15},
        "projection": "box", "scale": [2.0, 2.0]}},
    "upper_side": {"color": STUCCO[0], "tag": "wall", "texture": sheet("upper_side")},
    "roof": {"color": "#59606b", "tag": "roof", "texture": {
        "pattern": "tile", "colors": ["#59606b", "#3c424c"], "params": {"count": 2, "grout": 1},
        "projection": "planar", "axis": "y", "scale": [1.5, 1.5]}},
    "redtrim": {"color": "#8e1f2c", "palette": True},
    "dark": {"color": "#2b2832", "palette": True},
    "concrete": {"color": "#a8a69e", "palette": True},
    "steel": {"color": "#8a929e", "palette": True},
    "ac": {"color": "#cfd4da", "palette": True},
    "ball": {"color": "#c3ccd8", "palette": True, "smooth": True},
    "pink": {"color": "#ff7fb0", "palette": True},
    "awning": {"color": "#c4122e", "texture": {
        "pattern": "stripes", "colors": ["#c4122e", "#fff2dc"], "params": {"count": 4},
        "projection": "box", "scale": [1.6, 1.6]}},
    "sign": {"color": "#c4122e", "class": "emissive", "tag": "sign", "texture": sheet("sign")},
    "bulbs": {"color": "#fff06a", "class": "emissive", "tag": "sign", "texture": {
        "sheet": "art", "frames": ["bulbs_a", "bulbs_b"], "ticks": 10, "projection": "fit"}},
    "blade": {"color": "#1e2a8a", "class": "emissive", "tag": "sign", "texture": sheet("blade")},
    "storefront": {"color": "#26305e", "class": "emissive", "tag": "shopfront",
                   "texture": sheet("storefront", bits=8)},
    "lamp": {"color": "#e0301e", "class": "emissive", "tag": "lantern"},
    "banner": {"color": "#d81e1e", "double_sided": True, "texture": sheet("banner")},
    "vend": {"color": "#e8e8ea", "texture": sheet("vend")},
    "face": {"color": "#dfe6ee", "texture": sheet("face")},
    "side_door": {"color": "#2b2832", "texture": sheet("side_door")},
    "hut_door": {"color": "#cfd4da", "texture": sheet("hut_door")},
}


# ---- level 0 ---------------------------------------------------------------------------
def shell(roof_inside=True, decals=True):
    n = [box("ground", [W, G, D], [0, G / 2, 0], "tile", open=["bottom", "top"],
             decals=[{"id": "shopfront", "face": "back", "material": "storefront",
                      "size": [9.4, 2.6], "at": [0, r(0.05 + 1.3 - G / 2)]},
                     {"id": "side_door", "face": "left", "material": "side_door",
                      "size": [0.9, 2.1], "at": [-2.4, r(1.05 + 0.02 - G / 2)]}]
             if decals else None),
         box("cornice", [W + 0.4, CORN, D + 0.4], [0, G + CORN / 2, 0], "redtrim")]
    h = TOP - U0 if roof_inside else ROOF - U0
    n.append(box("upper", [UW, h, UD], [0, U0 + h / 2, 0], "stucco",
                 open=["bottom", "top"] if roof_inside else ["bottom"],
                 faces=dict({"left": "upper_side", "right": "upper_side"},
                            **({} if roof_inside else {"top": "roof"}))))
    if roof_inside:
        t = 0.15
        x0, x1, z0, z1 = -UW / 2 + t, UW / 2 - t, -UD / 2 + t, UD / 2 - t
        n += [yquad("roof", "roof", x0, x1, z0, z1, ROOF),
              zquad("parapet_in_s", "redtrim", x0, x1, ROOF, TOP, z0, facing=1),
              zquad("parapet_in_n", "redtrim", x0, x1, ROOF, TOP, z1, facing=-1),
              xquad("parapet_in_w", "redtrim", z0, z1, ROOF, TOP, x0, facing=1),
              xquad("parapet_in_e", "redtrim", z0, z1, ROOF, TOP, x1, facing=-1),
              yquad("coping_s", "redtrim", -UW / 2, UW / 2, -UD / 2, z0, TOP),
              yquad("coping_n", "redtrim", -UW / 2, UW / 2, z1, UD / 2, TOP),
              yquad("coping_w", "redtrim", -UW / 2, x0, z0, z1, TOP),
              yquad("coping_e", "redtrim", x1, UW / 2, z0, z1, TOP)]
    return n


def signs():
    sz = UZF - 0.15 + 0.02
    n = [box("sign", [8.4, 2.1, 0.3], [0, 5.35, sz], "dark", open=["front"],
             faces={"back": "sign"})]
    front = sz - 0.15
    for name, y in (("bulbs_top", 6.47), ("bulbs_bottom", 4.23)):
        n.append(zquad(name, "bulbs", -4.4, 4.4, y - 0.07, y + 0.07, front - 0.05))
    # the blade sign on the front-left corner, standing out from the wall
    n.append(box("blade", [0.25, 3.6, 1.2], [-UW / 2 + 0.5, 5.7, UZF - 0.58], "blade",
                 open=["top", "bottom", "front", "back"]))
    n.append(box("blade_cap", [0.31, 0.12, 1.26], [-UW / 2 + 0.5, 7.56, UZF - 0.58], "dark"))
    return n


def entrance():
    z = ZF - 0.55
    n = [box("canopy", [3.6, 0.08, 1.1], [0, 2.85, z], "awning", rotate=[-12, 0, 0]),
         box("step", [3.4, 0.12, 1.0], [0, 0.06, ZF - 0.48], "concrete",
             open=["bottom", "front"])]
    for i, x in enumerate((-1.7, 1.7)):
        n.append(box(f"post_{i}", [0.08, 2.72, 0.08], [x, 1.36, ZF - 1.0], "steel",
                     open=["top", "bottom"]))
    for i, x in enumerate((-1.1, 1.1)):
        n.append(cyl(f"lantern_{i}", 0.16, 0.4, [x, 2.4, ZF - 0.9], "lamp"))
    for i, x in enumerate((-2.3, 2.3)):
        n.append(sphere(f"guard_ball_{i}", 0.3, [x, 0.3, ZF - 0.7], "ball", 6, 4))
    # nobori banners at the front corners
    for i, px in enumerate((-W / 2 - 0.55, W / 2 + 0.55)):
        n.append(cyl(f"banner_pole_{i}", 0.03, 3.2, [px, 1.6, ZF - 0.4], "steel", segments=3,
                     caps=False))
        xa = px + 0.03 if i == 0 else px - 0.58
        n.append(zquad(f"banner_{i}", "banner", xa, xa + 0.55, 0.9, 3.1, ZF - 0.4))
    n.append(box("vend_machine", [0.75, 1.8, 0.65], [5.05, 0.9, ZF - 0.31], "ac",
                 open=["bottom", "front"], faces={"back": "vend"}))
    n.append(box("ac_unit", [0.4, 0.55, 0.9], [W / 2 + 0.18, 1.5, 1.6], "ac", open=["left"]))
    return n


def roof_top():
    cz = UZF + 1.6
    n = [box("roof_hut", [1.6, 1.0, 1.4], [2.6, ROOF + 0.49, UD / 2 - 1.3], "ac",
             open=["bottom"], faces={"back": "hut_door"}),
         cyl("pedestal", 0.7, 0.4, [0, ROOF + 0.19, cz], "redtrim", segments=8),
         sphere("mascot", 0.85, [0, ROOF + 0.38 + 0.82, cz], "ball", 8, 5,
                scale=[1, 1, 0.8]),
         zquad("mascot_face", "face", -0.42, 0.42, ROOF + 0.78, ROOF + 1.62, cz - 0.70),
         {"id": "antenna", "op": "cone", "radius": 0.07, "height": 0.42, "segments": 4,
          "material": "steel", "transform": {"translate": [0, ROOF + 2.21, cz]}},
         sphere("antenna_tip", 0.12, [0, ROOF + 2.45, cz], "pink", 4, 3)]
    for i, x in enumerate((-1.0, 1.0)):
        n.append(sphere(f"hand_{i}", 0.2, [x, ROOF + 1.0, cz - 0.15], "ball", 5, 3))
    return n


def level0():
    return shell() + signs() + entrance() + roof_top()


def level1():
    cz = UZF + 1.6
    n = shell(roof_inside=False)
    sz = UZF - 0.15 + 0.02
    n.append(box("sign", [8.4, 2.1, 0.3], [0, 5.35, sz], "dark", open=["front"],
                 faces={"back": "sign"}))
    n.append(box("blade", [0.25, 3.6, 1.2], [-UW / 2 + 0.5, 5.7, UZF - 0.58], "blade",
                 open=["top", "bottom", "front", "back"]))
    n.append(box("canopy", [3.6, 0.08, 1.1], [0, 2.85, ZF - 0.55], "awning",
                 rotate=[-12, 0, 0]))
    n.append(sphere("mascot", 0.85, [0, ROOF + 0.82, cz], "ball", 6, 4, scale=[1, 1, 0.8]))
    n.append(zquad("mascot_face", "face", -0.42, 0.42, ROOF + 0.4, ROOF + 1.24, cz - 0.70))
    return n


def level2():
    return [box("ground", [W, G, D], [0, G / 2, 0], "tile", open=["bottom", "top"]),
            box("upper", [W, ROOF - G, D], [0, (ROOF + G) / 2, 0], "stucco", open=["bottom"],
                faces={"top": "roof"}),
            box("sign", [8.4, 2.1, 0.3], [0, 5.35, ZF - 0.13], "dark", open=["front"],
                faces={"back": "sign"})]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "pachinko_parlour",
        "budget": {"triangles": 450},
        "sheets": {"art": {"image": "art/parlour_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               "solid", open=open)


def collision():
    t = 0.2
    cz = UZF + 1.6
    n = [solid("ground", -W / 2, W / 2, 0, G, -D / 2, D / 2, open=["bottom", "top"]),
         # the cornice is a ledge 0.2 m deep all round, 3.65 up: a grab
         solid("cornice", -W / 2 - 0.2, W / 2 + 0.2, G, U0, -D / 2 - 0.2, D / 2 + 0.2),
         solid("upper", -UW / 2, UW / 2, U0, ROOF, -UD / 2, UD / 2, open=["bottom"]),
         solid("parapet_s", -UW / 2, UW / 2, ROOF, TOP, -UD / 2, -UD / 2 + t, open=["bottom"]),
         solid("parapet_n", -UW / 2, UW / 2, ROOF, TOP, UD / 2 - t, UD / 2, open=["bottom"]),
         solid("parapet_w", -UW / 2, -UW / 2 + t, ROOF, TOP, -UD / 2 + t, UD / 2 - t,
               open=["bottom", "back", "front"]),
         solid("parapet_e", UW / 2 - t, UW / 2, ROOF, TOP, -UD / 2 + t, UD / 2 - t,
               open=["bottom", "back", "front"]),
         solid("roof_hut", 1.8, 3.4, ROOF, ROOF + 1.0, UD / 2 - 2.0, UD / 2 - 0.6,
               open=["bottom"]),
         # the mascot: stand on its head (8.85)
         solid("mascot", -0.85, 0.85, ROOF, ROOF + 2.05, cz - 0.7, cz + 0.7, open=["bottom"]),
         solid("blade", -UW / 2 + 0.38, -UW / 2 + 0.62, 3.9, 7.5, UZF - 1.18, UZF - 0.01),
         # the entrance canopy, flat, 2.9 up
         solid("canopy", -1.8, 1.8, 2.75, 2.95, ZF - 1.1, ZF - 0.01),
         solid("vend_machine", 4.67, 5.43, 0, 1.8, ZF - 0.64, ZF - 0.01, open=["bottom"])]
    for i, x in enumerate((-2.3, 2.3)):
        n.append(solid(f"guard_ball_{i}", x - 0.3, x + 0.3, 0, 0.6, ZF - 1.0, ZF - 0.4,
                       open=["bottom"]))
    return {
        "format": "mei-asset", "version": 1, "name": "pachinko_parlour_col",
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
    write("pachinko_parlour.asset.json", recipe())
    write("pachinko_parlour_col.asset.json", collision())
