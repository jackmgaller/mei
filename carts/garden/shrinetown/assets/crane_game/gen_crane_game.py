#!/usr/bin/env python3
"""Writes crane_game.asset.json and crane_game_col.asset.json next to this script.

Shrine town's UFO catcher: the lab's crane_game (781 triangles) cut to about 200. The teal tiled
cabinet with its slanted console, the glass case with gold posts, the striped marquee with its
sign, the siren lights and the star stay; the side sticker, the outlet label and the prize hole
are decals, the console's buttons are in its texture, the claw is a hub and three arms, and three
plush toys stand in for six. Every texture is 4-bit (the level's palettes, TEXTURES.md), and the
sign, the side sticker and the outlet label are stored at half width (the town's VRAM). Front is
-Z. 0.94 m wide, 1.28 m deep, 2.2 m tall.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def r4(v):
    return round(v, 4)


def tube(id_, a, b, radius, material, segments=3, caps=False, op="cylinder"):
    d = [b[i] - a[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in d))
    d = [c / n for c in d]
    rx = math.degrees(math.acos(max(-1, min(1, d[1]))))
    ry = math.degrees(math.atan2(d[0], d[2]))
    mid = [(a[i] + b[i]) / 2 for i in range(3)]
    return {"id": id_, "op": op, "radius": radius, "height": r4(n), "segments": segments,
            "caps": caps, "material": material,
            "transform": {"rotate": [r4(rx), r4(ry), 0], "translate": [r4(c) for c in mid]}}


# The console is the cabinet's sloped front: from (z -0.45, y 0.9) down to (z -0.75, y 0.8).
SLOPE = math.degrees(math.atan2(0.1, 0.3))
S, C = math.sin(math.radians(SLOPE)), math.cos(math.radians(SLOPE))
NORMAL = (0, C, -S)          # up and toward the front
ALONG = (0, S, C)            # up the slope, toward the back
MID = (0, 0.85, -0.6)


def on_console(lift, along=0.0, x=0.0):
    return [r4(x + MID[0]), r4(MID[1] + NORMAL[1] * lift + ALONG[1] * along),
            r4(MID[2] + NORMAL[2] * lift + ALONG[2] * along)]


CABINET = [[0.75, 0.0], [-0.45, 0.0], [-0.45, 0.9], [0.45, 0.9], [0.75, 0.8]]
STAR = [[0.0, 0.12], [-0.0306, 0.0421], [-0.1141, 0.0371], [-0.0495, -0.0161], [-0.0705, -0.0971],
        [-0.0, -0.052], [0.0705, -0.0971], [0.0495, -0.0161], [0.1141, 0.0371], [0.0306, 0.0421]]


def plush(id_, material, pos, yaw, ears=None):
    node = {"id": id_, "op": "group", "transform": {"rotate": [0, yaw, 0], "translate": pos},
            "children": [{"id": "body", "op": "sphere", "radius": 0.1, "rings": 2, "segments": 5,
                          "material": material, "transform": {"scale": [1.1, 0.95, 1.0]}}]}
    if ears == "bunny":
        for side, x in (("l", -0.045), ("r", 0.045)):
            node["children"].append(tube("ear" + side, (x, 0.05, 0), (x * 1.2, 0.26, 0.0), 0.022,
                                         material))
    return node


recipe = {
    "format": "mei-asset", "version": 1, "name": "crane_game",
    "budget": {"vertices": 400, "triangles": 200},
    "materials": {
        "cabinet": {"color": "#2fb7bd", "texture": {
            "pattern": "tile", "colors": ["#2fb7bd", "#e9f6f2", "#27a0a6"],
            "params": {"count": 2, "grout": 1}, "projection": "box", "scale": [0.32, 0.32]}},
        "floor": {"color": "#f3d6e0", "texture": {
            "pattern": "checker", "colors": ["#f6d9e4", "#f2a9c4"], "params": {"count": 2},
            "projection": "planar", "axis": "y", "scale": [0.2, 0.2]}},
        "stars": {"color": "#1d2a6b", "double_sided": True, "texture": {
            "pattern": "speckle", "colors": ["#1d2a6b", "#f4f0c8", "#ffd86b"], "size": 32,
            "params": {"density": 0.05, "seed": 5}, "projection": "planar", "axis": "z",
            "scale": [0.6, 0.6]}},
        "candy": {"color": "#d62678", "texture": {
            "pattern": "stripes", "colors": ["#d62678", "#fff3e2"], "params": {"count": 4},
            "projection": "box", "scale": [0.16, 0.16]}},
        "sign": {"color": "#d62678", "class": "emissive",
                 "texture": {"image": "art/sign.png", "bits": 4, "projection": "fit"}},
        "panel": {"color": "#3a285a", "texture": {"image": "art/panel.png", "bits": 4,
                                                  "projection": "fit"}},
        "side": {"color": "#fff4d6", "texture": {"image": "art/side.png", "bits": 4,
                                                 "projection": "fit"}},
        "label": {"color": "#ffec78", "texture": {"image": "art/label.png", "bits": 4,
                                                  "projection": "fit"}},
        "glare": {"color": "#ecf6ff", "double_sided": True,
                  "texture": {"image": "art/glare.png", "bits": 4, "projection": "fit"}},
        "gold": {"color": "#ffd23f", "palette": True, "double_sided": True},
        "chrome": {"color": "#c9ced6", "palette": True},
        "metal": {"color": "#6c7380", "palette": True},
        "dark": {"color": "#2a2230", "palette": True},
        "red": {"color": "#e8402f", "palette": True},
        "siren": {"color": "#ff5a4a", "class": "emissive"},
        "siren_b": {"color": "#4aa8ff", "class": "emissive"},
        "bear": {"color": "#b07a4a", "palette": True},
        "bunny": {"color": "#f4a8c0", "palette": True},
    },
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "base", "op": "extrude", "points": CABINET, "depth": 0.9, "material": "cabinet",
         "decals": [{"id": "sticker_r", "face": "front", "material": "side", "size": [0.64, 0.4],
                     "at": [-0.23, 0.42]}],
         "transform": {"rotate": [0, 90, 0]}},
        {"id": "console", "op": "box", "size": [0.8, 0.06, 0.3162], "open": ["bottom"],
         "material": "dark", "faces": {"top": "panel"},
         "transform": {"rotate": [-r4(SLOPE), 0, 0], "translate": on_console(0.005)}},
        {"id": "stick", "op": "cone", "radius": 0.032, "height": 0.12, "segments": 5, "caps": False,
         "material": "red",
         "transform": {"rotate": [-r4(SLOPE), 0, 0], "translate": on_console(0.035 + 0.04, -0.006, -0.224)}},
        {"id": "flap", "op": "box", "size": [0.4, 0.3, 0.06], "open": ["front"], "material": "dark",
         "decals": [{"id": "label", "face": "back", "material": "label", "size": [0.36, 0.06],
                     "at": [0, 0.08]}],
         "transform": {"translate": [-0.2, 0.31, -0.7525]}},
        {"id": "playfield", "op": "box", "size": [0.74, 0.06, 0.82], "open": ["bottom"],
         "material": "floor",
         "decals": [{"id": "prize_hole", "face": "top", "material": "dark", "size": [0.2, 0.2],
                     "at": [-0.25, -0.28]}],
         "transform": {"translate": [0, 0.92, 0]}},
        {"id": "post_lf", "op": "box", "size": [0.05, 0.86, 0.05], "open": ["top", "bottom"],
         "material": "gold", "transform": {"translate": [-0.39, 1.305, -0.42]}},
        {"id": "post_rf", "op": "box", "size": [0.05, 0.86, 0.05], "open": ["top", "bottom"],
         "material": "gold", "transform": {"translate": [0.39, 1.305, -0.42]}},
        {"id": "back_wall", "op": "mesh", "material": "stars",
         "vertices": [[-0.42, 0.93, 0.428], [0.42, 0.93, 0.428], [0.42, 1.72, 0.428],
                      [-0.42, 1.72, 0.428]], "faces": [[3, 2, 1, 0]]},
        {"id": "pane_front", "op": "mesh", "material": "glare",
         "vertices": [[0.0, 1.69, -0.447], [0.34, 1.69, -0.447], [0.34, 1.2, -0.447],
                      [0.0, 1.2, -0.447]], "faces": [[0, 1, 2, 3]]},
        {"id": "pane_right", "op": "mesh", "material": "glare",
         "vertices": [[0.447, 1.69, -0.38], [0.447, 1.69, 0.0], [0.447, 1.2, 0.0],
                      [0.447, 1.2, -0.38]], "faces": [[0, 1, 2, 3]]},
        {"id": "pane_left", "op": "mesh", "material": "glare",
         "vertices": [[-0.447, 1.69, 0.0], [-0.447, 1.69, -0.38], [-0.447, 1.2, -0.38],
                      [-0.447, 1.2, 0.0]], "faces": [[0, 1, 2, 3]]},
        {"id": "marquee", "op": "box", "size": [0.94, 0.24, 1.0], "open": ["bottom"],
         "material": "candy", "faces": {"back": "sign"}, "transform": {"translate": [0, 1.86, 0]}},
        {"id": "siren_l", "op": "cone", "radius": 0.055, "height": 0.1, "segments": 4, "caps": False,
         "material": "siren", "transform": {"translate": [-0.37, 2.0, 0.2]}},
        {"id": "siren_r", "op": "cone", "radius": 0.055, "height": 0.1, "segments": 4, "caps": False,
         "material": "siren_b", "transform": {"translate": [0.37, 2.0, 0.2]}},
        {"id": "topper", "op": "mesh", "material": "gold",
         "vertices": [[r4(x * 1.5), r4(2.07 + y * 1.5 + 0.03), 0.0] for x, y in STAR],
         "faces": [list(range(len(STAR) - 1, -1, -1))]},
        tube("rail_l", (-0.3, 1.69, -0.4), (-0.3, 1.69, 0.4), 0.025, "metal"),
        tube("rail_r", (0.3, 1.69, -0.4), (0.3, 1.69, 0.4), 0.025, "metal"),
        tube("bridge", (-0.32, 1.69, 0.12), (0.32, 1.69, 0.12), 0.03, "metal"),
        {"id": "claw_hub", "op": "cylinder", "radius": 0.05, "height": 0.07, "segments": 3,
         "caps": False, "material": "chrome", "transform": {"translate": [0.2, 1.615, 0.12]}},
        {"id": "claw", "op": "group", "transform": {"translate": [0.2, 1.58, 0.12]},
         "children": [tube("arm", (0.04, 0.0, 0), (0.09, -0.17, 0), 0.016, "red")],
         "modifiers": [{"op": "radial", "count": 3}]},
        plush("plush_bear", "bear", [0.28, 1.04, 0.12], -20),
        plush("plush_bunny", "bunny", [0.07, 1.04, 0.26], 10, ears="bunny"),
    ],
}
recipe["lod"] = {"levels": [{"distance": 22, "nodes": [
    {"id": "base", "op": "extrude", "points": CABINET, "depth": 0.9, "material": "cabinet",
     "transform": {"rotate": [0, 90, 0]}},
    {"id": "playfield", "op": "box", "size": [0.74, 0.06, 0.82], "open": ["bottom"],
     "material": "floor", "transform": {"translate": [0, 0.92, 0]}},
    {"id": "post_lf", "op": "box", "size": [0.05, 0.86, 0.05], "open": ["top", "bottom"],
     "material": "gold", "transform": {"translate": [-0.39, 1.305, -0.42]}},
    {"id": "post_rf", "op": "box", "size": [0.05, 0.86, 0.05], "open": ["top", "bottom"],
     "material": "gold", "transform": {"translate": [0.39, 1.305, -0.42]}},
    {"id": "back_wall", "op": "mesh", "material": "stars",
     "vertices": [[-0.42, 0.93, 0.428], [0.42, 0.93, 0.428], [0.42, 1.72, 0.428],
                  [-0.42, 1.72, 0.428]], "faces": [[3, 2, 1, 0]]},
    {"id": "marquee", "op": "box", "size": [0.94, 0.24, 1.0], "open": ["bottom"],
     "material": "candy", "faces": {"back": "sign"}, "transform": {"translate": [0, 1.86, 0]}},
]}], "cull": 90}

col = {
    "format": "mei-asset", "version": 1, "name": "crane_game_col",
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "cabinet", "op": "box", "size": [0.9, 0.9, 1.2], "open": ["top", "bottom"],
         "material": "solid", "transform": {"translate": [0, 0.45, -0.15]}},
        {"id": "case", "op": "box", "size": [0.94, 1.08, 1.0], "open": ["bottom"],
         "material": "solid", "transform": {"translate": [0, 1.44, 0]}},
    ],
}

for name, data in (("crane_game", recipe), ("crane_game_col", col)):
    with open(os.path.join(HERE, name + ".asset.json"), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
