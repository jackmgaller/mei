#!/usr/bin/env python3
"""Writes art/*.png and jizo.asset.json for the roadside jizo (run from anywhere; needs Pillow)."""
import json
import math
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "art"), exist_ok=True)

STONE = [(150, 148, 138), (138, 136, 128), (162, 160, 150), (126, 128, 118)]
INK = (52, 50, 46)
BLUSH = (214, 150, 140)


def noise(x, y, seed):
    h = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF


def face():
    """32 x 16, wraps once around the head; the face is centred on column FACE_U."""
    w, h = 32, 16
    im = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), STONE[noise(x, y, 3) % 4] + (255,))
    c = 8  # face centre column (placed to the front with the texture offset)
    px = im.putpixel
    # closed, smiling eyes: a small downward arc each
    for ex in (c - 3, c + 3):
        px((ex - 1, 9), INK + (255,))
        px((ex, 9), INK + (255,))
        px((ex + 1, 9), INK + (255,))
    # nose shadow, mouth
    px((c, 10), STONE[3] + (255,))
    px((c, 12), INK + (255,))
    px((c - 1, 11), INK + (255,))
    px((c + 1, 11), INK + (255,))
    # cheeks
    for bx in (c - 5, c + 5):
        px((bx, 11), BLUSH + (255,))
        px((bx + 1, 11), BLUSH + (255,))
    # the dot between the brows
    px((c, 7), (236, 226, 190, 255))
    im.save(os.path.join(HERE, "art", "jizo_face.png"))


def ring():
    """16 x 16 shakujo ring: a loop of metal with a clear middle, two small rings below."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    gold = (212, 178, 78, 255)
    dark = (140, 108, 44, 255)
    cx, cy = 7.5, 6.5
    for y in range(16):
        for x in range(16):
            d = math.hypot((x - cx) / 1.0, (y - cy) / 1.0)
            if 4.2 <= d <= 6.3:
                im.putpixel((x, y), gold if (x + y) % 5 else dark)
    for x, y in ((7, 13), (8, 13), (7, 14), (8, 14)):
        im.putpixel((x, y), gold)
    im.save(os.path.join(HERE, "art", "jizo_ring.png"))


def pinwheel():
    """16 x 16 kazaguruma: four vanes in two colours with a clear pinwheel gap between them."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    cols = [(224, 70, 70, 255), (250, 214, 90, 255), (80, 150, 220, 255), (240, 240, 232, 255)]
    # four triangles around the centre, each a quarter turned from the last
    for q in range(4):
        for y in range(16):
            for x in range(16):
                dx, dy = x - 7.5, y - 7.5
                for _ in range(q):
                    dx, dy = -dy, dx
                if 0 < dx <= 7 and -0.2 * dx - 0.4 <= dy <= 0.5 * dx - 0.6 and dy <= 0:
                    im.putpixel((x, y), cols[q])
    im.putpixel((7, 7), (60, 60, 60, 255))
    im.putpixel((8, 8), (60, 60, 60, 255))
    im.save(os.path.join(HERE, "art", "jizo_pinwheel.png"))


def recipe():
    circ = 2 * math.pi * 0.14
    mats = {
        "stone": {"color": "#989688", "tag": "stone",
                  "texture": {"pattern": "speckle", "size": 16,
                              "colors": ["#9a988a", "#8c8a7e", "#a6a496", "#7e8c6c"],
                              "params": {"density": 0.32, "seed": 5},
                              "projection": "box", "scale": [0.5, 0.5]}},
        "robe": {"color": "#989688", "smooth": True,
                 "texture": {"pattern": "speckle", "size": 32,
                             "colors": ["#9a988a", "#8c8a7e", "#a6a496", "#7e8c6c"],
                             "params": {"density": 0.28, "seed": 11},
                             "projection": "cylindrical", "scale": [0.5, 0.5]}},
        "face": {"color": "#989688", "smooth": True,
                 "texture": {"image": "art/jizo_face.png", "projection": "cylindrical",
                             "scale": [round(circ, 4), 0.34], "offset": [0.25, 0.5]}},
        "wool": {"color": "#c8352c", "smooth": True,
                 "texture": {"pattern": "checker", "size": 8, "colors": ["#c8352c", "#b02a24"],
                             "params": {"count": 4}, "projection": "cylindrical", "scale": [0.2, 0.12]}},
        "bib": {"color": "#d63a30", "double_sided": True},
        "bobble": {"color": "#f0e6d2"},
        "wood": {"color": "#7a5a3c"},
        "gold": {"color": "#d4b24e"},
        "ring": {"color": "#d4b24e", "double_sided": True,
                 "texture": {"image": "art/jizo_ring.png", "projection": "fit"}},
        "pinwheel": {"color": "#d04040", "double_sided": True,
                     "texture": {"image": "art/jizo_pinwheel.png", "projection": "fit"}},
        "cup": {"color": "#e8e4da"},
        "water": {"color": "#6aa0c8"},
        "pebble": {"color": "#8a8880"},
        "moss": {"color": "#5d7a45", "tag": "moss"},
    }
    P = math.pi
    nodes = [
        # the stone: two steps, a lotus drum, the robe
        {"id": "step_low", "op": "box", "size": [0.64, 0.09, 0.52], "open": ["bottom"],
         "material": "stone", "transform": {"translate": [0, 0.045, 0]}},
        {"id": "step_high", "op": "box", "size": [0.46, 0.09, 0.38], "open": ["bottom"],
         "material": "stone", "transform": {"translate": [0, 0.135, 0]}},
        {"id": "lotus", "op": "lathe", "segments": 8, "caps": False, "material": "robe",
         "profile": [[0.23, 0.0], [0.22, 0.05], [0.15, 0.09]],
         "transform": {"translate": [0, 0.18, 0]}},
        {"id": "robe", "op": "lathe", "segments": 8, "caps": False, "material": "robe",
         "profile": [[0.185, 0.0], [0.19, 0.06], [0.16, 0.2], [0.12, 0.32], [0.125, 0.38],
                     [0.085, 0.46]],
         "transform": {"translate": [0, 0.27, 0]}},
        {"id": "head", "op": "sphere", "radius": 0.14, "rings": 5, "segments": 8,
         "material": "face", "transform": {"translate": [0, 0.87, 0], "scale": [1, 1.04, 1]}},
        # red knitted cap, bib and a bobble
        {"id": "cap", "op": "lathe", "segments": 8, "caps": False, "material": "wool",
         "profile": [[0.155, 0.0], [0.145, 0.1], [0.046, 0.185]],
         "transform": {"translate": [0, 0.91, 0]}},
        {"id": "bobble", "op": "sphere", "radius": 0.028, "rings": 2, "segments": 5,
         "material": "bobble", "transform": {"translate": [0, 1.1, 0]}},
        {"id": "bib_ring", "op": "lathe", "segments": 8, "caps": False, "material": "bib",
         "profile": [[0.172, -0.085], [0.09, 0.0]],
         "transform": {"translate": [0, 0.75, 0]}},
        {"id": "bib_flap", "op": "mesh", "material": "bib",
         "vertices": [[-0.1, 0.72, -0.128], [0.1, 0.72, -0.128], [0.075, 0.56, -0.157],
                      [-0.075, 0.56, -0.157]],
         "faces": [[0, 3, 2, 1]]},
        # sleeves and hands
        {"id": "sleeves", "op": "group", "children": [
            {"id": "sleeve", "op": "cylinder", "radius": 0.055, "height": 0.21, "segments": 6,
             "caps": False, "material": "robe",
             "transform": {"rotate": [54, 0, 0], "translate": [0.135, 0.585, -0.125]}},
        ], "modifiers": [{"op": "mirror", "axis": "x"}]},
        {"id": "hand_staff", "op": "sphere", "radius": 0.038, "rings": 2, "segments": 5,
         "material": "robe", "transform": {"translate": [-0.15, 0.53, -0.2]}},
        {"id": "hand_jewel", "op": "sphere", "radius": 0.038, "rings": 2, "segments": 5,
         "material": "robe", "transform": {"translate": [0.15, 0.53, -0.2]}},
        {"id": "jewel", "op": "sphere", "radius": 0.032, "rings": 2, "segments": 6,
         "material": "gold", "transform": {"translate": [0.15, 0.59, -0.2]}},
        # the staff with its ring
        {"id": "staff", "op": "cylinder", "radius": 0.013, "height": 0.86, "segments": 5, "caps": False,
         "material": "wood", "transform": {"translate": [-0.15, 0.55, -0.2]}},
        {"id": "staff_ring", "op": "mesh", "material": "ring",
         "vertices": [[-0.2, 0.98, -0.2], [-0.1, 0.98, -0.2], [-0.1, 1.08, -0.2], [-0.2, 1.08, -0.2]],
         "faces": [[0, 3, 2, 1]]},
        # offerings on the lower step
        {"id": "cup", "op": "cylinder", "radius": 0.032, "height": 0.05, "segments": 6,
         "material": "cup", "transform": {"translate": [0.2, 0.112, -0.15]}},
        {"id": "pebble_a", "op": "sphere", "radius": 0.032, "rings": 2, "segments": 5,
         "material": "pebble", "transform": {"translate": [-0.2, 0.108, -0.17], "scale": [1.2, 0.7, 1]}},
        {"id": "pebble_b", "op": "sphere", "radius": 0.026, "rings": 2, "segments": 5,
         "material": "pebble", "transform": {"translate": [-0.15, 0.105, -0.2], "scale": [1, 0.7, 1]}},
        {"id": "pinwheel_stick", "op": "cylinder", "radius": 0.006, "height": 0.34, "segments": 3,
         "caps": False, "material": "wood", "transform": {"translate": [0.25, 0.26, -0.26]}},
        {"id": "pinwheel", "op": "mesh", "material": "pinwheel",
         "vertices": [[0.19, 0.38, -0.274], [0.31, 0.38, -0.274], [0.31, 0.5, -0.274],
                      [0.19, 0.5, -0.274]],
         "faces": [[0, 3, 2, 1]]},
        # moss creeping up the low step
        {"id": "moss", "op": "box", "size": [0.22, 0.012, 0.16], "material": "moss", "open": ["bottom"],
         "transform": {"translate": [-0.22, 0.095, 0.12]}},
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "jizo",
        "budget": {"vertices": 512, "triangles": 900},
        "materials": mats,
        "lighting": {"mode": "vertical", "ambient": 0.55},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


if __name__ == "__main__":
    face()
    ring()
    pinwheel()
    with open(os.path.join(HERE, "jizo.asset.json"), "w") as f:
        json.dump(recipe(), f, indent=1)
        f.write("\n")
