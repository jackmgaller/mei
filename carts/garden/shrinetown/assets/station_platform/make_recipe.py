#!/usr/bin/env python3
"""Writes station_platform.asset.json and station_platform_col.asset.json beside this script.

Shrine town's island platform, adapted from the asset lab's station_platform
(examples/assets/lab/station_platform): the viaduct, its piers, parapets, tracks and catenary
are left to the town's viaduct spans, and what stands on the deck is kept. The origin is the
middle of the platform at the deck (track bed) level; the platform's floor is 1.0 above it,
the canopy's top 3.8 above the floor. The tracks run along x at z = -4.1 (track 1) and +4.1
(track 2). Run `python3 make_recipe.py` after changing it; the recipes are the committed output.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

L = 20.0          # half length
W = 2.5           # half width
FLOOR = 1.0       # floor height above the deck
HOLE_X = (-1.5, 1.5)
HOLE_Z = 1.2
STAIR_END = 0.3   # the flight runs from x -1.5 (floor) down to here (y 0.05)
LANDING = 0.05
ROOF_LOW, ROOF_EDGE, ROOF_T, ROOF_HALF = 4.35, 4.6, 0.12, 2.9
FRAMES = [-15.0, -5.0, 5.0, 15.0]


def roof_bottom(z):
    return ROOF_LOW + (ROOF_EDGE - ROOF_LOW) * abs(z) / ROOF_HALF


def r(v):
    return round(v, 4)


MATERIALS = {
    "concrete": {"color": "#6a665e", "palette": True, "tag": "wall"},
    "coping": {"color": "#eceae4", "palette": True, "tag": "floor"},
    "green_steel": {"color": "#4f7f6a", "palette": True},
    "black": {"color": "#2c2a28", "palette": True},
    "shade": {"color": "#4a4a50", "palette": True, "tag": "floor"},
    "wood": {"color": "#5a3e2c", "palette": True, "tag": "wall"},
    "red": {"color": "#c8262c", "palette": True},
    "cat": {"color": "#e8a050", "palette": True},
    "lamp": {"color": "#f4fbff", "class": "emissive", "tag": "lamp"},
    "lantern": {"color": "#e04a2a", "class": "emissive", "tag": "lamp"},
    "floor": {
        "color": "#c4bead", "tag": "floor",
        "texture": {"pattern": "tile", "colors": ["#c6c0b0", "#a29c8e", "#bab3a2"],
                    "params": {"count": 2, "grout": 1}, "projection": "planar", "axis": "y", "scale": [2, 2]}},
    "tactile": {
        "color": "#f0c020", "tag": "floor",
        "texture": {"texels": ["00000000", "01100110", "01100110", "00000000",
                               "00000000", "01100110", "01100110", "00000000"],
                    "colors": ["#f0c020", "#ffe070"], "projection": "planar", "axis": "y", "scale": [1.2, 1.2]}},
    "tile_wall": {
        "color": "#e2d8c0", "tag": "wall",
        "texture": {"pattern": "tile", "colors": ["#e6dcc4", "#bfb39b", "#ddd0b4"],
                    "params": {"count": 4, "grout": 1}, "projection": "box", "scale": [2, 2]}},
    "roof": {
        "color": "#a9c4b4", "tag": "roof",
        "texture": {"pattern": "stripes", "colors": ["#b2ccbc", "#94b0a0"], "params": {"count": 4},
                    "size": 8, "projection": "box", "scale": [1.6, 1.6]}},
    "seats": {
        "color": "#e8862a",
        "texture": {"texels": ["1222222222222221", "1222222222222221", "2222222222222222", "2222222222222222",
                               "2222222222222222", "2222222222222222", "0333333333333330", "0333333333333330"],
                    "colors": ["#4a4440", "#c8701e", "#e8862a", "#d27a24"], "projection": "box", "scale": [0.45, 0.45]}},
    "stairs": {
        "color": "#b0aaa0", "tag": "stairs",
        "texture": {"texels": ["1111", "0000", "2222"] * 6,
                    "colors": ["#b0aaa0", "#f0c020", "#7a766e"], "projection": "fit"}},
    "opening": {
        "color": "#2c2a28",
        "texture": {"texels": ["2222", "1111", "0000", "0000", "0000", "0000"],
                    "colors": ["#1e1c1a", "#3a3836", "#e2d8c0"], "projection": "fit"}},
    "mark": {
        "color": "#e8782a", "tag": "floor",
        "texture": {"texels": ["00000000", "01111110", "00111100", "00011000"],
                    "colors": ["#eceae4", "#e8782a"], "projection": "fit"}},
    "fence": {"color": "#c8ccc6", "double_sided": True,
              "texture": {"sheet": "station", "cell": "fence", "projection": "fit"}},
    "poster": {"color": "#f0a060", "texture": {"sheet": "station", "cell": "poster", "projection": "fit"}},
    "name_board": {"color": "#f6f6f0", "tag": "sign",
                   "texture": {"sheet": "station", "cell": "name_board", "projection": "fit"}},
    "track1": {"color": "#1e2838", "tag": "sign", "texture": {"sheet": "station", "cell": "track1", "projection": "fit"}},
    "track2": {"color": "#1e2838", "tag": "sign", "texture": {"sheet": "station", "cell": "track2", "projection": "fit"}},
    "clock": {"color": "#f6f6f0", "texture": {"sheet": "station", "cell": "clock", "projection": "disc"}},
    "soba": {"color": "#ffd68c", "class": "emissive", "tag": "shop",
             "texture": {"sheet": "station", "cell": "soba", "projection": "fit"}},
    "vending": {"color": "#e0e4e8", "class": "emissive",
                "texture": {"sheet": "station", "cell": "vending", "projection": "fit"}},
    "bin_cans": {"color": "#e8e6de", "texture": {"sheet": "station", "cell": "bin_cans", "projection": "fit"}},
    "bin_burn": {"color": "#e8e6de", "texture": {"sheet": "station", "cell": "bin_burn", "projection": "fit"}},
}


def quad_up(x0, x1, z0, z1, y):
    """An upward face's corners, clockwise from above (top-left first in the top view)."""
    return [[x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0]]


def floor_mesh():
    """The floor in bands across the platform, with the stairwell's hole in the middle band."""
    verts, faces, mats = [], [], []

    def add(x0, x1, z0, z1, m):
        base = len(verts)
        verts.extend(quad_up(x0, x1, z0, z1, FLOOR))
        faces.append([base, base + 1, base + 2, base + 3])
        mats.append(m)

    for s in (-1, 1):
        bands = [(2.5, 2.3, "coping"), (2.3, 1.8, "floor"), (1.8, 1.5, "tactile")]
        for a, b, m in bands:
            z0, z1 = sorted((s * a, s * b))
            add(-L, L, z0, z1, m)
    hx0, hx1 = HOLE_X
    add(-L, hx0, -1.5, 1.5, "floor")
    add(hx1, L, -1.5, 1.5, "floor")
    add(hx0, hx1, -1.5, -HOLE_Z, "floor")
    add(hx0, hx1, HOLE_Z, 1.5, "floor")
    # The boarding marks for the last train (track 1 and track 2), on the east floor piece (face 7).
    decals = [{"id": "mark_1", "face": 7, "material": "mark", "size": [0.8, 0.4], "at": [8.0, -1.2]},
              {"id": "mark_2", "face": 7, "material": "mark", "size": [0.8, 0.4], "at": [8.0, 1.2]}]
    return {"id": "platform_floor", "op": "mesh", "material": "floor", "vertices": verts, "faces": faces,
            "face_materials": mats, "decals": decals}


def platform_sides():
    v = [[-L, 0, -W], [L, 0, -W], [L, FLOOR, -W], [-L, FLOOR, -W],
         [L, 0, W], [-L, 0, W], [-L, FLOOR, W], [L, FLOOR, W]]
    # Front (-Z) seen from the front: top-left, top-right, bottom-right, bottom-left.
    faces = [[3, 2, 1, 0], [7, 6, 5, 4], [2, 7, 4, 1], [6, 3, 0, 5]]
    return {"id": "platform_sides", "op": "mesh", "material": "concrete", "vertices": v, "faces": faces}


def end_fences():
    return {"id": "end_fences", "op": "group", "children": [
        {"id": "fence", "op": "mesh", "material": "fence",
         "vertices": [[L, FLOOR + 1.1, -W], [L, FLOOR + 1.1, W], [L, FLOOR, W], [L, FLOOR, -W]],
         "faces": [[0, 1, 2, 3]]}],
        "modifiers": [{"op": "mirror", "axis": "x"}]}


def stairwell():
    hx0, hx1 = HOLE_X
    top = FLOOR + 1.0
    zin = HOLE_Z + 0.01
    nodes = []
    nodes.append({"id": "stairs", "op": "mesh", "material": "stairs",
                  "vertices": [[hx0, FLOOR, zin], [STAIR_END, LANDING, zin], [STAIR_END, LANDING, -zin], [hx0, FLOOR, -zin]],
                  "faces": [[0, 1, 2, 3]]})
    nodes.append({"id": "landing", "op": "mesh", "material": "shade",
                  "vertices": quad_up(STAIR_END, hx1 - 0.14, -zin, zin, LANDING), "faces": [[0, 1, 2, 3]]})
    h = top - LANDING
    yc = (top + LANDING) / 2
    nodes.append({"id": "head_wall", "op": "box", "size": [0.2, r(h + 0.06), 2.6], "material": "tile_wall", "open": ["bottom"],
                  "decals": [{"id": "way_down", "face": "left", "material": "opening", "size": [2.2, 0.88],
                              "at": [0, r(LANDING + 0.01 + 0.44 - yc - 0.03)]}],
                  "transform": {"translate": [hx1 - 0.05, r(yc + 0.03), 0]}})
    nodes.append({"id": "side_walls", "op": "group", "children": [
        {"id": "wall", "op": "box", "size": [hx1 - hx0, h, 0.15], "material": "tile_wall", "open": ["bottom"],
         "decals": [{"id": "poster", "face": "back", "material": "poster", "size": [0.5, 0.75],
                     "at": [-0.6, r(FLOOR + 0.15 + 0.375 - yc)]}],
         "transform": {"translate": [0, r(yc), -(HOLE_Z + 0.075)]}}],
        "modifiers": [{"op": "mirror", "axis": "z"}]})
    return nodes


def canopy():
    nodes = []
    pts = [[-0.15, FLOOR - 0.02], [0.15, FLOOR - 0.02], [0.15, 3.55], [2.8, 4.33], [2.8, 4.62], [0, 4.37],
           [-2.8, 4.62], [-2.8, 4.33], [-0.15, 3.55]]
    frames = []
    for i, x in enumerate(FRAMES):
        frames.append({"id": f"frame{i}", "op": "extrude", "material": "green_steel", "depth": 0.25, "points": pts,
                       "transform": {"rotate": [0, 90, 0], "translate": [x, 0, 0]}})
    nodes.append({"id": "frames", "op": "group", "children": frames})
    rp = [[-ROOF_HALF, ROOF_EDGE], [0, ROOF_LOW], [ROOF_HALF, ROOF_EDGE],
          [ROOF_HALF, ROOF_EDGE + ROOF_T], [0, ROOF_LOW + ROOF_T], [-ROOF_HALF, ROOF_EDGE + ROOF_T]]
    nodes.append({"id": "roof", "op": "extrude", "material": "roof", "depth": 34.0, "points": rp,
                  "transform": {"rotate": [0, 90, 0]}})
    lights = []
    for i, x in enumerate([-10.0, 0.0, 10.0]):
        z0, z1 = 1.13, 1.27
        y0, y1 = roof_bottom(z0) - 0.04, roof_bottom(z1) - 0.04
        x0, x1 = x - 0.75, x + 0.75
        # Facing down: the up-facing order reversed.
        lights.append({"id": f"light{i}", "op": "mesh", "material": "lamp",
                       "vertices": [[x0, r(y0), z0], [x1, r(y0), z0], [x1, r(y1), z1], [x0, r(y1), z1]],
                       "faces": [[0, 1, 2, 3]]})
    nodes.append({"id": "lights", "op": "group", "children": lights, "modifiers": [{"op": "mirror", "axis": "z"}]})
    return nodes


def name_board(nid, x):
    return {"id": nid, "op": "group", "transform": {"translate": [x, 0, 0]}, "children": [
        {"id": "legs", "op": "group", "children": [
            {"id": "leg", "op": "box", "size": [0.04, 1.04, 0.04], "material": "green_steel", "open": ["bottom", "top"],
             "transform": {"translate": [1.0, FLOOR + 0.52, 0]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        {"id": "board", "op": "box", "size": [2.5, 0.95, 0.12], "material": "black",
         "faces": {"back": "name_board", "front": "name_board"},
         "transform": {"translate": [0, FLOOR + 1.475, 0]}}]}


def track_sign(nid, z, mat):
    yb = roof_bottom(z)
    return {"id": nid, "op": "group", "transform": {"translate": [3.2, 0, z]}, "children": [
        {"id": "hanger", "op": "box", "size": [0.04, r(yb + 0.03 - 3.7), 0.04], "material": "concrete",
         "open": ["top", "bottom"], "transform": {"translate": [0, r((yb + 0.03 + 3.7) / 2), 0]}},
        {"id": "plate", "op": "box", "size": [0.06, 0.4, 1.25], "material": "black",
         "faces": {"left": mat, "right": mat}, "transform": {"translate": [0, 3.5, 0]}}]}


def clock():
    return {"id": "clock", "op": "group", "transform": {"translate": [-4.0, 0, 0]}, "children": [
        {"id": "hanger", "op": "box", "size": [0.03, 0.2, 0.03], "material": "concrete", "open": ["top", "bottom"],
         "transform": {"translate": [0, 4.26, 0]}},
        {"id": "face", "op": "cylinder", "radius": 0.3, "height": 0.1, "segments": 8, "material": "clock",
         "faces": {"side": "green_steel"}, "transform": {"rotate": [0, 0, 90], "translate": [0, 3.88, 0]}}]}


def bench(nid, x, z, yaw):
    pts = [[-0.21, 0.42], [0.21, 0.42], [0.21, 0.95], [0.16, 0.95], [0.16, 0.48], [-0.21, 0.48]]
    return {"id": nid, "op": "group", "transform": {"rotate": [0, yaw, 0], "translate": [x, FLOOR, z]}, "children": [
        {"id": "seat", "op": "extrude", "material": "seats", "depth": 1.8, "points": pts,
         "transform": {"rotate": [0, -90, 0]}},
        {"id": "legs", "op": "group", "children": [
            {"id": "leg", "op": "box", "size": [0.05, 0.44, 0.34], "material": "green_steel", "open": ["bottom"],
             "transform": {"translate": [0.75, 0.21, 0]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}]}]}


def cat():
    return {"id": "cat", "op": "group", "transform": {"translate": [12.75, FLOOR + 0.47, -0.62]}, "children": [
        {"id": "body", "op": "sphere", "radius": 0.16, "rings": 3, "segments": 6, "material": "cat",
         "transform": {"scale": [1.3, 0.65, 1.0], "translate": [0.12, 0.09, 0]}},
        {"id": "head", "op": "sphere", "radius": 0.09, "rings": 3, "segments": 5, "material": "cat",
         "transform": {"translate": [-0.12, 0.1, -0.06]}},
        {"id": "ears", "op": "group", "children": [
            {"id": "ear", "op": "cone", "radius": 0.035, "height": 0.07, "segments": 3, "caps": False, "material": "cat",
             "transform": {"translate": [-0.12, 0.2, -0.015]}}],
         "modifiers": [{"op": "mirror", "axis": "z", "offset": -0.06}]},
        {"id": "tail", "op": "box", "size": [0.3, 0.05, 0.05], "material": "cat",
         "transform": {"rotate": [0, 10, 0], "translate": [0.1, 0.03, -0.17]}}]}


def soba():
    x = -10.0
    return {"id": "soba_stand", "op": "group", "transform": {"translate": [x, 0, 0]}, "children": [
        {"id": "kiosk", "op": "box", "size": [3.6, 2.6, 1.6], "material": "wood", "open": ["bottom"],
         "decals": [{"id": "front", "face": "back", "material": "soba", "size": [3.3, 1.65], "at": [0, -0.25]}],
         "transform": {"translate": [0, FLOOR + 1.3, 0]}},
        {"id": "eave", "op": "box", "size": [3.9, 0.08, 0.6], "material": "green_steel",
         "transform": {"translate": [0, FLOOR + 2.0, -1.08]}},
        {"id": "lantern", "op": "cylinder", "radius": 0.18, "height": 0.42, "segments": 6, "material": "lantern",
         "transform": {"translate": [1.95, FLOOR + 1.73, -1.2]}}]}


def kiosk_props():
    return [
        {"id": "vending_machine", "op": "box", "size": [0.95, 1.8, 0.7], "material": "red", "open": ["bottom"],
         "faces": {"front": "vending"}, "transform": {"translate": [12.5, FLOOR + 0.9, 0.4]}},
        {"id": "bin_cans", "op": "box", "size": [0.5, 0.9, 0.45], "material": "coping", "open": ["bottom"],
         "faces": {"front": "bin_cans"}, "transform": {"translate": [13.75, FLOOR + 0.45, 0.3]}},
        {"id": "bin_burn", "op": "box", "size": [0.5, 0.9, 0.45], "material": "coping", "open": ["bottom"],
         "faces": {"front": "bin_burn"}, "transform": {"translate": [14.35, FLOOR + 0.45, 0.3]}},
    ]


def lod1():
    hx0, hx1 = HOLE_X
    return [
        {"id": "slab", "op": "box", "size": [2 * L, FLOOR, 2 * W], "material": "concrete", "open": ["bottom"],
         "faces": {"top": "floor"}, "transform": {"translate": [0, FLOOR / 2, 0]}},
        {"id": "stair_head", "op": "box", "size": [hx1 - hx0, 1.0, 2.7], "material": "tile_wall", "open": ["bottom"],
         "transform": {"translate": [0, FLOOR + 0.49, 0]}},
        {"id": "columns", "op": "group", "children": [
            {"id": "column", "op": "box", "size": [0.25, 3.4, 0.3], "material": "green_steel", "open": ["bottom", "top"],
             "transform": {"translate": [FRAMES[0], FLOOR + 1.7, 0]}}],
         "modifiers": [{"op": "array", "count": 4, "step": [10, 0, 0]}]},
        {"id": "roof", "op": "extrude", "material": "roof", "depth": 34.0,
         "points": [[-ROOF_HALF, ROOF_EDGE], [0, ROOF_LOW], [ROOF_HALF, ROOF_EDGE], [ROOF_HALF, ROOF_EDGE + ROOF_T],
                    [0, ROOF_LOW + ROOF_T], [-ROOF_HALF, ROOF_EDGE + ROOF_T]],
         "transform": {"rotate": [0, 90, 0]}},
        {"id": "board_w", "op": "box", "size": [2.5, 1.9, 0.08], "material": "black", "open": ["bottom"],
         "faces": {"back": "name_board", "front": "name_board"}, "transform": {"translate": [-16.5, FLOOR + 0.98, 0]}},
        {"id": "board_e", "op": "box", "size": [2.5, 1.9, 0.08], "material": "black", "open": ["bottom"],
         "faces": {"back": "name_board", "front": "name_board"}, "transform": {"translate": [7.5, FLOOR + 0.98, 0]}},
        {"id": "kiosk", "op": "box", "size": [3.6, 2.6, 1.6], "material": "wood", "open": ["bottom"],
         "faces": {"back": "soba"}, "transform": {"translate": [-10.0, FLOOR + 1.3, 0]}},
        {"id": "vending_machine", "op": "box", "size": [0.95, 1.8, 0.7], "material": "red", "open": ["bottom"],
         "faces": {"front": "vending"}, "transform": {"translate": [12.5, FLOOR + 0.9, 0.4]}},
        end_fences(),
    ]


def lod2():
    return [
        {"id": "slab", "op": "box", "size": [2 * L, FLOOR, 2 * W], "material": "concrete", "open": ["bottom"],
         "faces": {"top": "coping"}, "transform": {"translate": [0, FLOOR / 2, 0]}},
        {"id": "roof", "op": "extrude", "material": "roof", "depth": 34.0,
         "points": [[-ROOF_HALF, ROOF_EDGE], [0, ROOF_LOW], [ROOF_HALF, ROOF_EDGE], [ROOF_HALF, ROOF_EDGE + ROOF_T],
                    [0, ROOF_LOW + ROOF_T], [-ROOF_HALF, ROOF_EDGE + ROOF_T]],
         "transform": {"rotate": [0, 90, 0]}},
        {"id": "kiosk", "op": "box", "size": [3.6, 2.6, 1.6], "material": "wood", "open": ["bottom"],
         "faces": {"back": "soba"}, "transform": {"translate": [-10.0, FLOOR + 1.3, 0]}},
    ]


def recipe():
    nodes = [floor_mesh(), platform_sides(), end_fences()]
    nodes += stairwell()
    nodes += canopy()
    nodes += [name_board("name_board_west", -16.5), name_board("name_board_east", 7.5),
              track_sign("track_sign_1", -1.45, "track1"), track_sign("track_sign_2", 1.45, "track2"),
              clock(), soba(),
              bench("bench_w_north", -6.5, -0.55, 0), bench("bench_w_south", -6.5, 0.55, 180),
              bench("bench_east", 12.5, -0.55, 0), cat()]
    nodes += kiosk_props()
    return {
        "format": "mei-asset", "version": 1, "name": "station_platform",
        "budget": {"vertices": 1100, "triangles": 900},
        "sheets": {"station": {"image": "art/station_sheet.png"}},
        "materials": MATERIALS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
        "lod": {"levels": [{"distance": 30, "nodes": lod1()}, {"distance": 70, "nodes": lod2()}], "band": 2},
    }


def collision():
    hx0, hx1 = HOLE_X

    def box(nid, x0, x1, y0, y1, z0, z1, open_=("bottom",)):
        n = {"id": nid, "op": "box", "size": [r(x1 - x0), r(y1 - y0), r(z1 - z0)], "material": "solid",
             "transform": {"translate": [r((x0 + x1) / 2), r((y0 + y1) / 2), r((z0 + z1) / 2)]}}
        if open_:
            n["open"] = list(open_)
        return n

    hz = HOLE_Z
    sv = [[-L, FLOOR, -W], [L, FLOOR, -W], [L, FLOOR, W], [-L, FLOOR, W],
          [hx0, FLOOR, -W], [hx1, FLOOR, -W], [hx1, FLOOR, W], [hx0, FLOOR, W],
          [hx0, FLOOR, -hz], [hx1, FLOOR, -hz], [hx1, FLOOR, hz], [hx0, FLOOR, hz],
          [-L, 0, -W], [L, 0, -W], [L, 0, W], [-L, 0, W]]
    slab = {"id": "slab", "op": "mesh", "material": "solid", "vertices": sv,
            "faces": [[3, 7, 4, 0], [6, 2, 1, 5], [7, 6, 10, 11], [8, 9, 5, 4],
                      [0, 1, 13, 12], [2, 3, 15, 14], [1, 2, 14, 13], [3, 0, 12, 15]]}
    nodes = [
        slab,
        {"id": "stairs", "op": "extrude", "material": "solid", "depth": 2 * hz - 0.04,
         "points": [[hx0, FLOOR], [hx0, 0], [STAIR_END, 0], [STAIR_END, LANDING]]},
        box("wall_n", hx0, hx1, 0, FLOOR + 1.0, -hz - 0.15, -hz),
        box("wall_s", hx0, hx1, 0, FLOOR + 1.0, hz, hz + 0.15),
        box("head_wall", hx1 - 0.2, hx1 + 0.05, 0, FLOOR + 1.04, -hz - 0.1, hz + 0.1),
        box("fence_w", -L, -L + 0.2, FLOOR, FLOOR + 1.1, -W, W),
        box("fence_e", L - 0.2, L, FLOOR, FLOOR + 1.1, -W, W),
        box("kiosk", -11.8, -8.2, FLOOR, FLOOR + 2.6, -0.8, 0.8),
        box("vending", 12.0, 13.0, FLOOR, FLOOR + 1.8, 0.05, 0.75),
        box("bins", 13.5, 14.6, FLOOR, FLOOR + 0.9, 0.07, 0.53),
        box("benches_w", -7.4, -5.6, FLOOR, FLOOR + 0.48, -0.76, 0.76),
        box("bench_e", 11.6, 13.4, FLOOR, FLOOR + 0.48, -0.76, -0.34),
        box("board_w", -17.75, -15.25, FLOOR + 1.0, FLOOR + 1.95, -0.1, 0.1),
        box("board_e", 6.25, 8.75, FLOOR + 1.0, FLOOR + 1.95, -0.1, 0.1),
        {"id": "roof", "op": "extrude", "material": "solid", "depth": 34.0,
         "points": [[-ROOF_HALF, ROOF_EDGE - 0.08], [0, ROOF_LOW - 0.08], [ROOF_HALF, ROOF_EDGE - 0.08],
                    [ROOF_HALF, ROOF_EDGE + ROOF_T], [0, ROOF_LOW + ROOF_T], [-ROOF_HALF, ROOF_EDGE + ROOF_T]],
         "transform": {"rotate": [0, 90, 0]}},
    ]
    for i, x in enumerate(FRAMES):
        nodes.append(box(f"column{i}", x - 0.15, x + 0.15, FLOOR, ROOF_LOW - 0.05, -0.15, 0.15, ("bottom", "top")))
    return {"format": "mei-asset", "version": 1, "name": "station_platform_col",
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": {"mode": "vertical", "ambient": 0.5},
            "verification": {"required": True, "depth": True, "perspective": True},
            "nodes": nodes}


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    write("station_platform.asset.json", recipe())
    write("station_platform_col.asset.json", collision())
