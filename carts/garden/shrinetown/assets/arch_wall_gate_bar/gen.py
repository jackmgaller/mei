#!/usr/bin/env python3
"""Writes arch_wall_gate_bar (barred), arch_wall_gate_bar_lifted (the bar set down) and the
barred bar's collision.  Run: python3 gen.py   (the files land beside this script)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'tools'))
from assetkit import author as A  # noqa: E402

MATS = {
    "wood": {"color": "#8a6446",
             "texture": {"pattern": "grain", "size": 16, "colors": ["#8a6446", "#6a4a36", "#a07c58"],
                         "params": {"rings": 3, "waves": 1, "amplitude": 2},
                         "projection": "box", "scale": [1.0, 0.5]}},
    "wood_dark": {"color": "#5a3e2c", "palette": True},
}
LEN = 5.6   # x -2.8 .. 2.8; the last 0.3 m at each end sits in the gate posts' sockets


def parts(lifted):
    """Two beams and a stile.  Barred: standing in the opening.  Lifted: set down flat."""
    src = [("beam_0", [LEN, 0.22, 0.22], "wood", ["left", "right"], 1.0),
           ("beam_1", [LEN, 0.22, 0.22], "wood", ["left", "right"], 1.9),
           ("stile", [0.14, 1.1, 0.12], "wood_dark", ["top", "bottom"], 1.45)]
    out = []
    for nid, size, mat, op, y in src:
        if not lifted:
            out.append(A.box(nid, size, [0, y, 0], mat, open=op))
        else:   # turned about X: height becomes depth.  Lies on the ground, 1.2 m to the ridge side
            out.append(A.box(nid, size, [0, 0.11, 1.2 + (y - 1.45)], mat, open=op,
                             rotate=[90, 0, 0]))
    return out


far = [A.box(f"beam_{k}", [LEN, 0.22, 0.22], [0, y, 0], "wood",
             open=["left", "right", "top", "bottom"]) for k, y in enumerate((1.0, 1.9))]
A.write(HERE / "arch_wall_gate_bar.asset.json",
        A.recipe("arch_wall_gate_bar", MATS, parts(False), budget=30,
                 lod=A.lod([(30, far)], cull=90)))
A.write(HERE / "arch_wall_gate_bar_lifted.asset.json",
        A.recipe("arch_wall_gate_bar_lifted", MATS, parts(True), budget=30))

# collision: the barred bar is a wall the width of the opening, 2.3 m tall, 0.3 m thick
A.write(HERE / "arch_wall_gate_bar_col.asset.json",
        A.collision("arch_wall_gate_bar_col", [A.box("wall", [5.0, 2.3, 0.3], [0, 1.15, 0])]))
