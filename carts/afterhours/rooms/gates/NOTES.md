# Room 2, the ticket gates: dressing notes

The concourse at the top of the platform's stair, after the last train. Most of the light comes
from the station office: a ceiling light and a desk lamp, falling out through its window and open
door as a warm trapezoid on the floor. Also lit:

- the gates' green lamps and blue card pads;
- three ticket machines with sloping, glowing consoles;
- the coin lockers under a tube, their gap dark: the hiding place, a missing module with its dust
  outline on the floor;
- the stairwell, a real hole with its steps going down and cool light at the bottom;
- the way up to the passage, bright in the east wall;
- tactile lines from the stair's head through the wide aisle (z −2.05) to the way up, with a
  branch to the office's window.

## Files (mine)

| File | What |
|---|---|
| `dress_gates.py` | Writes `dressed/*.asset.json`, `dressed/art/*.png` and, with `--placements`, `gates.placements.json`. Imports `make_gates.py` for the plan's numbers and `../arrival/dresskit.py` for the helpers |
| `dressed/` | **The recipe folder for `make_level1.py`'s `ROOMS`**, in place of `rooms/gates/greybox` |

Captures: `python3 carts/afterhours/rooms/arrival/capture.py gates --verify` writes `shots/`.

## Signature props (once in the level)

- **Coin lockers.**
- **Automatic ticket gates.**
- **Ticket machines.**
- **The station office**: desk with its log, CRT monitor, desk lamp, chair, cabinet, the door
  open.
- **The level's one round wall clock** (0:12).
- **The office pictogram sign.**
- **The fare map**: a lightbox of coloured lines.
- **Two paper notices.**
- **Cardboard boxes on the lockers.**

No vending machine, plant, bench or lightbox ad here.

## Numbers

| Recipe | Triangles | Placed |
|---|---|---|
| `r2_concourse`: floor in two textured halves, the walls, the stairwell and its steps, lockers, gates, barrier, machines, the office and its contents. 220 triangles of light refinement (cap, reached) | 632 | once |
| `r2_glass`: the office window and the barrier's panel. Unlit, so refinement leaves it alone | 20 | once, collision `none` |
| **Room** | **652** of 2,500 (the greybox: about 200) | |

Collision: `r2_concourse_col` is the greybox's shell collision under a new name. Its floor still
covers the stairwell, as the greybox's did. The wall map keeps the thief out of the well.

- **Asset Checker:** both recipes pass in depth mode.
- **Textures:** 65,830 bytes of VRAM (region `gates`).
- **Drawn at 60° by `capture.py`**, the room alone: 351 triangles, 72,828 CPU cycles, 258,427
  GPU cycles. With the stand-ins and a cone: 507 triangles, 104,009 CPU, 272,178 GPU.
- **In the cart** (scenario 42, with the HUD, guard and cone): at most 538 triangles, 123,174 CPU
  and 282,580 GPU cycles a frame. The greybox drew 304, 82,075 and 193,477.
- **Checks:** the World Checker passes. `solutions.py --check` clears the room (tick 1,507).
  Scenario 42 passes, as do all 25 of `tests/check.sh`.

## For the level lead

- `ROOMS` in `make_level1.py`: `rooms/gates/dressed` instead of `rooms/gates/greybox`.
  `gates.placements.json` now names only `r2_*` recipes in `dressed/`.
- Everything in "Must stay" is where the plan has it:
  - the gates are 0.98 m high with real (not cut) tops;
  - the barrier is a 0.72 m wall with glass to 0.98 m;
  - the office walls and jamb are cut at 1 m with pale tops;
  - the window is glass from 0.8 m;
  - the lockers are 2.0 m, with the 1 m gap;
  - the stairwell railings are 0.95 m with real tops;
  - the machines are under 1 m.
- Outside the plan's footprints:
  - the stairwell's railings stand 0.12 m outside the well (z −1.6 … −1.48, x −4.3 … −4.18), on
    the floor;
  - the office's open door leaf and its furniture are inside the office, where nobody walks.
- The fare map is on the back wall (x 2.5 … 5.5), not over the machines: the front wall is cut at
  1 m, so a map over the machines would be gone.

## What fought me

- **The stairwell** first read as a pale box: its far wall was lit too strongly. It now has a
  darker wall, yellow nosings and a dim light at the bottom, and it reads as a hole.
- **The gates' faces toward the camera were black.** No light reaches them from the camera's
  side. The recipe's directional fill now comes from there (`direction` toward −z, `diffuse`
  0.2).
- **Coplanar faces where low walls meet the well's edge, and where the barrier meets the last
  gate.** The Asset Checker caught both.
