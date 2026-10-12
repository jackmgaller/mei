#!/usr/bin/env python3
"""Writes shrine town's city bus: art/bus_sheet.png (+ .sheet.json), city_bus.asset.json and
city_bus_col.asset.json.

Adapted from the lab model (examples/assets/lab/city_bus, 986 triangles), whose pictures it
reads: the Midori city bus, 11 x 2.5 m, cream and green with the yellow stripe, the 07 Midoridai
Ekimae destination blind, the driver in the windscreen, passengers in the windows, the side ad.
Same size and outline. The cut: the six stacked bands of the body (288 triangles) are one loft
with the livery painted on as a vertical stripe texture; the side windows are four strips (the
lab's window pictures side by side) instead of fourteen panes; the wheels are lathes with the
hub painted on their outer face; headlamps, lamps and lights are flat plates. The bus faces -Z
(its front) and its doors are on its left (-X), the kerb side in Japan.

Levels: L1 from 30 m, L2 from 60 m, culled at 150 m. The bus is a mover (spec 6.4: plaza to
the east edge and back); its collision is one box, roof at 3.0, so a player can ride on it.

Run: python3 carts/garden/shrinetown/assets/city_bus/make_city_bus.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "city_bus", "art")
ART = os.path.join(HERE, "art")

CREAM = "#efe6cd"
GREEN = "#2e8b57"
YELLOW = "#f2c230"
BAND = "#1f2a30"
DARK = "#202226"

# the lab's plan outline: chamfered front corners, rounded rear ones
OUTLINE = [[0.6, -5.5], [1.0596, -5.3096], [1.25, -4.85], [1.25, 5.05], [1.1182, 5.3682],
           [0.8, 5.5], [-0.8, 5.5], [-1.1182, 5.3682], [-1.25, 5.05], [-1.25, -4.85],
           [-1.0596, -5.3096], [-0.6, -5.5]]
ROOF = [[0.37, -5.3], [0.8296, -5.1096], [1.02, -4.65], [1.02, 4.85], [0.8882, 5.1682],
        [0.57, 5.3], [-0.57, 5.3], [-0.8882, 5.1682], [-1.02, 4.85], [-1.02, -4.65],
        [-0.8296, -5.1096], [-0.37, -5.3]]
OUTLINE8 = [[0.8, -5.5], [1.25, -5.05], [1.25, 5.2], [0.95, 5.5], [-0.95, 5.5], [-1.25, 5.2],
            [-1.25, -5.05], [-0.8, -5.5]]
ROOF8 = [[0.6, -5.3], [1.02, -4.88], [1.02, 5.0], [0.75, 5.3], [-0.75, 5.3], [-1.02, 5.0],
         [-1.02, -4.88], [-0.6, -5.3]]
SIDE = 1.285        # side plates stand 3.5 cm off the body's side (x = 1.25)
FRONT = -5.535      # front plates 3.5 cm ahead of the front face
REAR = 5.535


# ---- art -------------------------------------------------------------------------------
def lab(name):
    return Image.open(os.path.join(LAB, name)).convert("RGB")


def strip(names):
    """The lab's 32 x 32 windows side by side, a 3-texel gap (the dark band) between."""
    w = 32 * len(names) + 3 * (len(names) - 1)
    im = Image.new("RGB", (w, 32), BAND)
    for i, n in enumerate(names):
        im.paste(lab(n), (i * 35, 0))
    return im


def livery():
    """8 x 128, one repeat 4 m tall from y 4 down to y 0 (row r is y = 4 - r / 32): the
    cream roof, the dark window band, the cream sill, the yellow stripe, green below."""
    im = Image.new("RGB", (8, 128), CREAM)
    d = ImageDraw.Draw(im)

    def band(y0, y1, c):     # y0 < y1 in metres
        d.rectangle([0, round((4 - y1) * 32), 7, round((4 - y0) * 32) - 1], fill=c)

    band(0.0, 1.03, GREEN)
    band(1.03, 1.09, YELLOW)
    band(1.09, 1.25, CREAM)
    band(1.25, 2.5, BAND)
    band(0.0, 0.42, "#256f46")          # the darker skirt
    return im


def wheel():
    """24 x 24 disc: the tyre's black ring and the lab's hub inside it."""
    im = Image.new("RGB", (24, 24), "#18181b")
    hub = lab("hub.png").resize((14, 14), Image.NEAREST)
    mask = Image.new("L", (14, 14), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 13, 13], fill=255)
    im.paste(hub, (5, 5), mask)
    return im


def draw_art():
    os.makedirs(ART, exist_ok=True)
    cells = {
        "livery": livery(),
        "win_r1": strip(["win_a.png", "win_b.png", "win_c.png", "win_a.png"]),
        "win_r2": strip(["win_c.png", "win_b.png", "win_a.png", "win_c.png", "win_b.png"]),
        "win_l1": strip(["win_a.png", "win_c.png"]),
        "win_l2": strip(["win_a.png", "win_c.png", "win_b.png", "win_a.png", "win_b.png"]),
        "door": lab("door.png"),
        "screen_l": lab("screen_l.png"),
        "screen_r": lab("screen_r.png"),
        "sign": lab("sign.png"),
        "rear_sign": lab("rear_sign.png"),
        "plate": lab("plate.png"),
        "ad": lab("ad.png"),
        "wheel": wheel(),
    }
    # pack in rows of 256
    sheet = Image.new("RGB", (256, 512), (0, 0, 0))
    rects, x, y, rh = {}, 0, 0, 0
    for name, im in cells.items():
        if x + im.width > 256:
            x, y, rh = 0, y + rh, 0
        sheet.paste(im, (x, y))
        rects[name] = [x, y, im.width, im.height]
        x += im.width
        rh = max(rh, im.height)
    sheet = sheet.crop((0, 0, 256, y + rh))
    sheet.save(os.path.join(ART, "bus_sheet.png"))
    with open(os.path.join(ART, "bus_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": rects}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r4(v):
    return [round(a, 4) for a in v]


def box(id, size, pos, mat, open=None, faces=None, rot=None):
    n = {"id": id, "op": "box", "size": r4(size), "material": mat,
         "transform": {"translate": r4(pos)}}
    if rot:
        n["transform"]["rotate"] = rot
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    return n


def quad(id, mat, corners):
    """A plate: corners top-left, top-right, bottom-right, bottom-left as seen from outside."""
    return {"id": id, "op": "mesh", "material": mat, "vertices": [r4(c) for c in corners],
            "faces": [[0, 1, 2, 3]]}


def side_plate(id, mat, side, z0, z1, y0, y1):
    """A plate on the left (-X) or right (+X) side, from z0 to z1 (z0 < z1)."""
    if side < 0:      # seen from -X: right is -Z
        return quad(id, mat, [[-SIDE, y1, z1], [-SIDE, y1, z0], [-SIDE, y0, z0], [-SIDE, y0, z1]])
    return quad(id, mat, [[SIDE, y1, z0], [SIDE, y1, z1], [SIDE, y0, z1], [SIDE, y0, z0]])


def front_plate(id, mat, x0, x1, y0, y1, z=FRONT):
    return quad(id, mat, [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]])


def rear_plate(id, mat, x0, x1, y0, y1, z=REAR):
    """Seen from +Z: right is -X."""
    return quad(id, mat, [[x1, y1, z], [x0, y1, z], [x0, y0, z], [x1, y0, z]])


def body(outline, roof, id="body"):
    """The body with the livery painted on, and the roof's rounded edge as a cream loft sunk
    1 cm into its top (so the livery's box projection never lands on the near-flat bevel)."""
    return [{"id": id, "op": "loft", "material": "livery", "faces": {"top": "cream", "bottom": "dark"},
             "sections": [{"y": 0.3, "points": outline}, {"y": 2.95, "points": outline}]},
            {"id": "roof", "op": "loft", "material": "cream",
             "sections": [{"y": 2.94, "points": outline}, {"y": 3.08, "points": roof}]}]


def wheels(segments=8):
    n = []
    for side in (-1, 1):
        for z, w, tag in ((-3.1, 0.32, "f"), (3.1, 0.42, "r")):
            n.append({"id": f"wheel_{'l' if side < 0 else 'r'}{tag}", "op": "lathe",
                      "segments": segments, "caps": False, "material": "wheel",
                      "profile": [[0.5, -w / 2], [0.5, w / 2 - 0.04], [0.0, w / 2]],
                      "transform": {"rotate": [0, 0, 90 if side < 0 else -90],
                                    "translate": [side * (1.33 - w / 2), 0.5, z]}})
    return n


def arches():
    n = []
    for side in (-1, 1):
        for z, tag in ((-3.1, "f"), (3.1, "r")):
            pts = [[z - 0.62, 0.3], [z - 0.62, 0.5], [z - 0.4384, 0.9384], [z, 1.12],
                   [z + 0.4384, 0.9384], [z + 0.62, 0.5], [z + 0.62, 0.3]]
            x = side * SIDE
            verts = [[x, y, zz] for zz, y in pts]
            face = list(range(7)) if side < 0 else list(range(6, -1, -1))
            n.append({"id": f"arch_{'l' if side < 0 else 'r'}{tag}", "op": "mesh",
                      "material": "dark", "vertices": [r4(v) for v in verts], "faces": [face]})
    return n


def sides(detail=True):
    n = [side_plate("win_r1", "win_r1", 1, -4.8, -0.5, 1.32, 2.44),
         side_plate("win_r2", "win_r2", 1, -0.4, 5.0, 1.32, 2.44),
         side_plate("win_l1", "win_l1", -1, -3.82, -2.1, 1.32, 2.44),
         side_plate("win_l2", "win_l2", -1, -0.8, 5.0, 1.32, 2.44),
         side_plate("door1", "door", -1, -4.95, -3.95, 0.5, 2.44),
         side_plate("door2", "door", -1, -1.95, -0.95, 0.5, 2.44)]
    if detail:
        n += [side_plate("ad_r", "ad", 1, -1.1, 1.1, 0.62, 0.96),
              side_plate("ad_l", "ad", -1, 0.0, 1.95, 0.62, 0.92),
              side_plate("route_l", "rear_sign", -1, -4.62, -4.12, 2.6, 2.78),
              side_plate("route_r", "rear_sign", 1, -4.62, -4.12, 2.6, 2.78)]
    return n


def front(detail=True):
    n = [front_plate("screen_l", "screen_l", -1.12, -0.04, 1.34, 2.46),
         front_plate("screen_r", "screen_r", 0.04, 1.12, 1.34, 2.46),
         front_plate("blind", "sign", -0.98, 0.98, 2.58, 2.9)]
    if detail:
        n += [front_plate("plate", "plate", -0.24, 0.24, 0.62, 0.8),
              front_plate("lamp_l", "lamp", -1.0, -0.72, 0.72, 0.92),
              front_plate("lamp_r", "lamp", 0.72, 1.0, 0.72, 0.92),
              front_plate("signal_l", "amber", -0.98, -0.74, 0.99, 1.07),
              front_plate("signal_r", "amber", 0.74, 0.98, 0.99, 1.07),
              front_plate("grille", "dark", -0.35, 0.35, 0.9, 1.0),
              box("bumper_f", [2.4, 0.2, 0.18], [0, 0.42, -5.6], "bumper"),
              box("visor", [2.2, 0.05, 0.12], [0, 2.53, -5.58], "dark")]
    return n


def rear(detail=True):
    n = [rear_plate("rear_glass", "screen_l", -0.9, 0.9, 1.4, 2.42),
         rear_plate("rear_blind", "rear_sign", -0.3, 0.3, 2.62, 2.8)]
    if detail:
        n += [rear_plate("plate_r", "plate", -0.24, 0.24, 0.62, 0.8),
              rear_plate("tail_l", "red", -1.08, -0.82, 0.83, 1.03),
              rear_plate("tail_r", "red", 0.82, 1.08, 0.83, 1.03),
              rear_plate("backup_l", "lamp", -0.77, -0.63, 0.91, 0.99),
              rear_plate("backup_r", "lamp", 0.63, 0.77, 0.91, 0.99),
              box("bumper_r", [2.4, 0.22, 0.16], [0, 0.42, 5.6], "bumper"),
              {"id": "exhaust", "op": "cylinder", "radius": 0.06, "height": 0.4, "segments": 4,
               "caps": False, "material": "dark",
               "transform": {"rotate": [90, 0, 0], "translate": [0.7, 0.3, 5.5]}}]
    return n


def mirrors():
    n = []
    for s, t in ((-1, "l"), (1, "r")):
        n += [box(f"mirror_arm_{t}", [0.5, 0.07, 0.07], [s * 1.5, 2.1, -5.25], "grey"),
              box(f"mirror_{t}", [0.12, 0.5, 0.16], [s * 1.8, 2.0, -5.25], "grey")]
    return n


def roof_kit():
    return [box("ac", [1.4, 0.18, 1.5], [0, 3.13, 0.6], "grey", open=["bottom"],
                faces={"top": "dark"}),
            box("vent_f", [0.5, 0.1, 0.4], [0, 3.1, -3.4], "grey", open=["bottom"]),
            box("vent_r", [0.5, 0.1, 0.4], [0, 3.1, 3.1], "grey", open=["bottom"])]


# ---- materials -------------------------------------------------------------------------
def cell(name, bits=4, emissive=False, color="#ffffff", projection="fit", **tex):
    m = {"color": color, "texture": {"sheet": "bus", "cell": name, "bits": bits,
                                     "projection": projection, **tex}}
    if emissive:
        m["class"] = "emissive"
    return m


MATERIALS = {
    "livery": cell("livery", color=GREEN, projection="box", scale=[2, 4]),
    "cream": {"color": CREAM, "palette": True, "tag": "roof"},
    "dark": {"color": DARK, "palette": True},
    "bumper": {"color": "#3a3d44", "palette": True},
    "grey": {"color": "#aeb4bc", "palette": True},
    "lamp": {"color": "#fff3b0", "palette": True},
    "amber": {"color": "#ff9a1f", "palette": True},
    "red": {"color": "#d8342c", "palette": True},
    "win_r1": cell("win_r1", 8, color="#305c70"),
    "win_r2": cell("win_r2", 8, color="#305c70"),
    "win_l1": cell("win_l1", 8, color="#305c70"),
    "win_l2": cell("win_l2", 8, color="#305c70"),
    "door": cell("door", color="#305c70"),
    "screen_l": cell("screen_l", color="#305c70"),
    "screen_r": cell("screen_r", color="#305c70"),
    "sign": cell("sign", 8, emissive=True, color="#ffb028"),
    "rear_sign": cell("rear_sign", emissive=True, color="#ffb028"),
    "plate": cell("plate", color="#f0f0ec"),
    "ad": cell("ad", 8, color=CREAM),
    "wheel": cell("wheel", color="#18181b", projection="disc"),
}


def level0():
    return (body(OUTLINE, ROOF) + wheels(8) + arches() + sides() + front() + rear()
            + mirrors() + roof_kit())


def level1():
    return (body(OUTLINE8, ROOF8) + wheels(6) + sides(False) + front(False) + rear(False)
            + [box("ac", [1.4, 0.18, 1.5], [0, 3.13, 0.6], "grey", open=["bottom"])])


def level2():
    rect = [[1.25, -5.5], [1.25, 5.5], [-1.25, 5.5], [-1.25, -5.5]]
    return [{"id": "body", "op": "loft", "material": "livery", "faces": {"top": "cream", "bottom": "dark"},
             "sections": [{"y": 0.3, "points": rect}, {"y": 3.05, "points": rect}]},
            front_plate("screen", "screen_r", -1.12, 1.12, 1.34, 2.46, z=-5.53)]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "city_bus",
        "budget": {"vertices": 600, "triangles": 600},
        "sheets": {"bus": {"image": "art/bus_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 30, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 150, "band": 2},
    }


def collision():
    return {
        "format": "mei-asset", "version": 1, "name": "city_bus_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": {"solid": {"color": "#c8c4b8"}},
        "nodes": [box("body", [2.5, 3.0, 11.0], [0, 1.5, 0], "solid", open=["bottom"])],
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("city_bus.asset.json", recipe())
    write("city_bus_col.asset.json", collision())
