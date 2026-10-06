#!/usr/bin/env python3
"""Writes arch_komainu.asset.json and arch_komainu_col.asset.json (python3 gen_komainu.py), and each lion
alone (arch_komainu_a, arch_komainu_un, with their _col), to flank a wide approach.

A pair of guardian lion-dogs on plinths, facing -Z: the open-mouthed "a" lion at -X and the
closed-mouthed, horned "un" lion at +X (as a visitor on the approach sees them). Each sits on
its haunches with its front legs straight, a big head with eyes and a muzzle, a lobed mane
framing the head and a flame-shaped tail; about 150 triangles a lion."""
import json, math, os
here = os.path.dirname(os.path.abspath(__file__))

TOP = 0.5           # plinth top
HEAD_Y = 1.29       # head centre
HEAD_Z = -0.20


def mane_outline(lobes, cx, cy, r_out, r_in, sx=1.0):
    """A star of `lobes` points around (cx, cy), one lobe straight up."""
    pts = []
    for i in range(lobes * 2):
        a = math.pi / 2 + i * math.pi / lobes
        r = r_out if i % 2 == 0 else r_in
        pts.append([round(cx + r * sx * math.cos(a), 4), round(cy + r * math.sin(a), 4)])
    return pts


def body_sections(sections):
    """Trapezoid loft sections: (y, z_back, w_back, z_front, w_front)."""
    out = []
    for y, zb, wb, zf, wf in sections:
        out.append({"y": y, "points": [[-wb / 2, zb], [wb / 2, zb], [wf / 2, zf], [-wf / 2, zf]]})
    return out


def lion(tag, x, open_mouth):
    def T(y, z, **k):
        return dict(translate=[x, y, z], **k)
    nodes = [
        {"id": tag + "_plinth", "op": "box", "size": [0.8, TOP, 0.9], "material": "stone",
         "open": ["bottom"], "transform": T(TOP / 2, 0)},
        # sitting body: wide rump (the haunches) on the plinth, rising to an upright chest
        {"id": tag + "_body", "op": "loft", "material": "stone", "caps": False,
         "sections": body_sections([
             (TOP - 0.01, 0.36, 0.66, -0.18, 0.46),
             (0.72, 0.30, 0.60, -0.24, 0.42),
             (0.95, 0.10, 0.46, -0.36, 0.44),
             (1.16, -0.04, 0.32, -0.33, 0.36)]),
         "transform": T(0, 0)},
        # straight front legs, flared at the paws, from the plinth up into the head
        {"id": tag + "_legs", "op": "group", "material": "carved",
         "modifiers": [{"op": "mirror", "axis": "x"}],
         "children": [{"id": "leg", "op": "box", "size": [0.12, 0.51, 0.13],
                       "open": ["top", "bottom"],
                       "modifiers": [{"op": "taper", "top": 0.85, "bottom": 1.3}],
                       "transform": {"translate": [0.14, 0, 0]}}],
         "transform": T(TOP - 0.01 + 0.255, -0.29)},
        {"id": tag + "_head", "op": "box", "size": [0.44, 0.36, 0.36], "material": "carved",
         "open": ["bottom"], "faces": {"back": "face"},
         "transform": T(HEAD_Y, HEAD_Z)},
        # the mane: a ring of curls framing the head and cheeks
        {"id": tag + "_mane", "op": "extrude", "material": "mane_side", "depth": 0.22,
         "faces": {"back": "mane", "front": "mane"},
         "points": mane_outline(7, 0, HEAD_Y - 0.05, 0.42, 0.33, sx=1.0),
         "transform": T(0, -0.06)},
        {"id": tag + "_tail", "op": "extrude", "material": "mane_side", "depth": 0.12,
         "faces": {"back": "mane", "front": "mane"},
         "points": [[0.06, 0.78], [0.34, 0.70], [0.46, 0.92], [0.40, 1.12], [0.30, 1.36],
                    [0.10, 1.06]],
         "transform": T(0, 0, rotate=[0, -90, 0])},
    ]
    if open_mouth:
        nodes += [
            {"id": "a_jaw_upper", "op": "box", "size": [0.26, 0.10, 0.14], "material": "carved",
             "open": ["front"], "faces": {"back": "snout_a"}, "transform": T(1.235, -0.43)},
            {"id": "a_mouth", "op": "box", "size": [0.21, 0.13, 0.02], "material": "mouth",
             "open": ["front", "top", "bottom", "left", "right"],
             "transform": T(1.12, -0.405)},
            {"id": "a_jaw_lower", "op": "box", "size": [0.22, 0.055, 0.12], "material": "carved",
             "open": ["front"], "faces": {"back": "jaw_a"}, "transform": T(1.07, -0.42)},
        ]
    else:
        nodes += [
            {"id": "un_muzzle", "op": "box", "size": [0.26, 0.17, 0.14], "material": "carved",
             "open": ["front"], "faces": {"back": "snout_un"}, "transform": T(1.20, -0.43)},
            {"id": "un_horn", "op": "cone", "radius": 0.05, "height": 0.14, "segments": 4,
             "material": "carved", "transform": T(HEAD_Y + 0.18 + 0.06, -0.26)},
        ]
    return nodes


nodes = lion("a", -0.55, True) + lion("un", 0.55, False)


def lod_lion(tag, x):
    def T(y, z, **k):
        return dict(translate=[x, y, z], **k)
    return [
        {"id": tag + "_plinth", "op": "box", "size": [0.8, TOP, 0.9], "material": "stone",
         "open": ["bottom"], "transform": T(TOP / 2, 0)},
        {"id": tag + "_body", "op": "loft", "material": "stone", "caps": False,
         "sections": body_sections([
             (TOP - 0.01, 0.36, 0.58, -0.30, 0.44),
             (1.16, -0.04, 0.30, -0.30, 0.32)]),
         "transform": T(0, 0)},
        {"id": tag + "_head", "op": "box", "size": [0.44, 0.36, 0.40], "material": "carved",
         "open": ["bottom"], "transform": T(HEAD_Y, HEAD_Z - 0.04)},
        {"id": tag + "_mane", "op": "extrude", "material": "mane_side", "depth": 0.22,
         "points": mane_outline(3, 0, HEAD_Y - 0.05, 0.42, 0.37),
         "transform": T(0, -0.06)},
    ]


recipe = {
    "format": "mei-asset", "version": 1, "name": "arch_komainu",
    "budget": {"triangles": 320},
    "sheets": {"komainu": {"image": "art/komainu.png"}},
    "materials": {
        "stone": {"color": "#a49e90", "texture": {"image": "art/forest_stone.png",
                  "projection": "box", "scale": [1.0, 1.0]}},
        "carved": {"color": "#b4ae9e", "palette": True},
        "mane_side": {"color": "#8e887c", "palette": True},
        "mouth": {"color": "#2c2a28", "palette": True},
        "face": {"color": "#b4ae9e", "texture": {"sheet": "komainu", "cell": "face",
                 "projection": "fit"}},
        "snout_un": {"color": "#b4ae9e", "texture": {"sheet": "komainu", "cell": "snout_un",
                     "projection": "fit"}},
        "snout_a": {"color": "#b4ae9e", "texture": {"sheet": "komainu", "cell": "snout_a",
                    "projection": "fit"}},
        "jaw_a": {"color": "#b4ae9e", "texture": {"sheet": "komainu", "cell": "jaw_a",
                  "projection": "fit"}},
        "mane": {"color": "#8e887c", "texture": {"sheet": "komainu", "cell": "mane",
                 "projection": "fit"}},
    },
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
    "lod": {"levels": [{"distance": 24, "nodes": lod_lion("a", -0.55) + lod_lion("un", 0.55)}],
            "cull": 60},
}
col = {
    "format": "mei-asset", "version": 1, "name": "arch_komainu_col",
    "budget": {"triangles": 40},
    "materials": {"solid": {"color": "#ffffff", "palette": True}},
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": [
        {"id": "plinth_%s" % t, "op": "box", "size": [0.8, 0.5, 0.9], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [x, 0.25, 0]}}
        for t, x in (("a", -0.55), ("un", 0.55))
    ] + [
        # the lion, head and mane: 0.5 to 1.66 high, z -0.50 to 0.38, sunk 1 cm into the plinth
        {"id": "body_%s" % t, "op": "box", "size": [0.64, 1.17, 0.88], "material": "solid",
         "open": ["bottom"], "transform": {"translate": [x, 0.49 + 1.17 / 2, -0.06]}}
        for t, x in (("a", -0.55), ("un", 0.55))
    ],
}


def single(tag, budget):
    """One lion of the pair at x = 0, to flank an approach wider than the pair (the world places
    arch_komainu_a on the left of the path as a visitor sees it and arch_komainu_un on the right)."""
    open_mouth = tag == "a"
    nodes = lion(tag, 0.0, open_mouth)
    r = dict(recipe, name="arch_komainu_" + tag, budget={"triangles": budget},
             nodes=nodes, lod={"levels": [{"distance": 24, "nodes": lod_lion(tag, 0.0)}], "cull": 60})
    c = dict(col, name="arch_komainu_%s_col" % tag, budget={"triangles": 20},
             nodes=[dict(n, transform={"translate": [0.0] + n["transform"]["translate"][1:]})
                    for n in col["nodes"] if n["id"].endswith("_" + tag)])
    return r, c


singles = [r for t in ("a", "un") for r in single(t, 160)]
for name, r in [("arch_komainu", recipe), ("arch_komainu_col", col)] + [(r["name"], r) for r in singles]:
    with open(os.path.join(here, name + ".asset.json"), "w") as f:
        json.dump(r, f, indent=1)
        f.write("\n")
