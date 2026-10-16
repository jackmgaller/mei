# The ocean gallery: notes

This is room 3 of the aquarium stage (`levels/aquarium/ROUTE.md`): the last public gallery,
entered from the jellyfish gallery and left by the staff door into quarantine. It is the
aquarium after closing, lit by its tanks:

- the ocean window across the back wall, with a turtle, a ray, a shark, a silver school, rock,
  kelp and light shafts;
- a glass column with a shoal of sardines turning round its light;
- a teal coral cube, and small tanks set into the side walls;
- cyan guide lights in the floor, a bench, stanchions, a pillar cut at 1 m, a night cleaner's
  cart.

Beyond the way in at the front left, the jellyfish gallery's violet passage ends. Beyond the staff
door, a plain service corridor runs back to a door under a QUARANTINE sign. The play (the walls,
the watchers, the solution) is the level lead's `../PLAN.md`, played from J's
`levels/aquarium/ocean/ocean.play.json`; none of it moved.

## Shots

| File | What |
|---|---|
| `aquarium_stage_from_jellyfish.png` | In the built stage: scenario 83 (the stage's rooms, each entered by each way in) at frame 520. The thief has just come in from the jellyfish gallery |
| `aquarium_stage_from_quarantine.png` | The same at frame 600, the thief come back in by the staff door |
| `aquarium_60.png` | The game's camera (`dr_view.akr`'s framing for this room) drawn by `capture.py`. The stand-ins act out a moment of PLAN.md's solution: the thief in the pillar's sight shadow, the watchman looking over the room, the keeper on the cube's far side |
| `aquarium_45.png`, `aquarium_75.png` | Each framed so the floor's front edge spans the picture |
| `*_x3.png` | The same, scaled up three times pixel for pixel |
| `compare.png` | 45°, 60° and 75° side by side |
| `relight_60.png` | History: the sketch, the trial relight and the first relight at 60° |

## How it is made and checked

- `../make_aquarium.py` writes the five recipes, `../aquarium.placements.json` and `../art/*.png`.
  It needs Pillow and NumPy; text uses Figtree and Zen Maru Gothic from `tools/fonts/`.
- `../capture.py --build-dir build-dorobo-sketch --verify` runs the Asset Checker, packs the
  recipes in the room's region's slots (`8,6,5,4,3,20-24`), draws each view and writes
  `numbers.json`.
- The stage:
  - `make B=build-dorobo-sketch build-dorobo-sketch/carts/afterhours.mei` builds every world. In
    the aquarium world's World Checker: 0 hard failures, 0 over thresholds.
  - `MEIC=… RUN=… WORLDS=build-dorobo-sketch/cart-worlds/afterhours sh carts/afterhours/tests/check.sh`
    passes, all 54 scenarios. Scenario 83 enters this room by both doors.
  - J's `levels/aquarium/solutions.py` did not exist yet, so the stage's tapes could not be
    played.
- **Light.** `room_lights()` holds 13 point lights:
  - the window (4, soft shadows);
  - the glass column and the coral cube (soft shadows);
  - the exit sign;
  - the 4 small wall tanks;
  - the jellyfish gallery's violet, low beyond the way in, so the cut front wall shades it except
    through the doorway;
  - the corridor's tube, which reaches the room through the staff door only.

  The kit bakes them into the walls and props, with at most 160 refinement triangles.
  `paint_floor()` paints the emissive floor from the same lights. A light behind a wall reaches
  the floor only through that wall's opening (each light's `through`). The floor also gets the
  water's shimmer, soft shadows, the guide studs and a glow round the coral cube.
- **Textures:** 12 tiles, 60,541 bytes, in the region's slots `8,6,5,4,3,20-24`. That is 67,136
  of the region's 327,680 bytes (`mei_world.py textures`). No slot 7 and no 4-bit palettes
  250-251.

| Recipe | Triangles | Vertices | In the stage |
|---|---|---|---|
| `aq_room` | 788 | 547 | placed as `r5_room_shell`, with the level lead's collision `aq_col` |
| `aq_tanks` | 1,041 | 1,179 | placed as `r5_tanks`, no collision |
| **room** | **1,829** | | of 2,500 |
| `standin_thief`, `standin_guard`, `sight_cone` | 116, 168, 32 | | for `capture.py` only |

## For the stage (2026-10-15)

- **The way in** now leads from the jellyfish gallery. Beyond the front wall's gap is a short
  passage (x −5.18 … −3.42, z −4.5 … −3.18):
  - a dark floor and walls cut at 1 m;
  - violet glow strips along their feet;
  - violet light falling through the doorway onto the room's floor.

  The lift's warm light is gone.
- **The staff door** is open in the right pier now: 0.82 m wide (x 4.84 … 5.66), 2.1 m tall,
  with a recessed lintel and a light strip under it. The old door decal is gone. Beyond it, x
  4.86 … 6.07 and z 3.15 … 5.0, is a plain service corridor:
  - grey floor and walls, a fluorescent tube, two pipes along the tank's side;
  - at its end, a dark doorway under a QUARANTINE sign.

  Its white light reaches the room through the door. Seen at 60°, the corridor floor shows only
  through the doorway, since the 3.2 m pier hides the rest; its end wall and sign show above the
  pier.
- **The glass column** holds 60 sardines in a three-turn helix (3 triangles each) instead of the
  jellyfish. The glass and its light are cool blue; the glass is `add`, so the shoal keeps its
  contrast. The sign reads イワシ / SARDINES. The glass footprint is unchanged (r 0.75 glass, r 0.76
  plinth).
- Nothing in play moved: the walls, glass, pillar, bench, rope, cart, sign and doors still match
  `ocean.play.json` and `aq_col`.

## Costs in `capture.py`, per frame

These frames have the room, the thief, two guards and their cones. The budgets are 1,000,000 CPU
and 2,000,000 GPU cycles.

| Pitch | Triangles drawn | CPU cycles | GPU cycles | The glass (GPU / CPU) |
|---|---|---|---|---|
| 45° | 1,436 | 287,562 (29 %) | 373,885 (18.7 %) | 32,039 / 24,915 |
| 60° | 1,430 | 287,010 (29 %) | 394,471 (19.7 %) | 30,637 / 24,920 |
| 75° | 1,381 | 282,481 (28 %) | 388,528 (19.4 %) | 25,795 / 24,823 |

At 60°, before this pass (the plan's room in level 1) the frame was 1,286 triangles drawn,
259,610 CPU and 381,779 GPU cycles. The additions cost 144 drawn triangles and about 27,000 CPU
cycles (2.7 % of the budget):

- the corridor and the passage (about 100 triangles);
- the sardines (180 triangles, where the jellyfish were 156);
- the new walls' share of the 160 refinement triangles.

With a third guard and the cones drawn twice, the 60° frame is 308,277 CPU and 422,034 GPU
cycles.

In the stage's scenario 83 the worst frame is room 2's (the great tank, not this room): 710,458
CPU cycles.

## What fought me

- **A wall in front of the camera cannot be seen past.** The way in faces the camera, so the
  passage beyond it lies below the room on screen. The game's framing for this room shows it; the
  sketch's tight 60° framing put it off the bottom edge. It is kept low (cut at 1 m) so it hides
  nothing.
- **The corridor behind a 3.2 m pier** shows at 60° only through its door and above the pier. Its
  light carries it: a white doorway in the blue room.
- **A sardine shoal behind half-blended glass** read as an empty tube. `add` glass (as the
  window's) fixed it.
- **New junctions** (lintel, corridor, passage) each needed the usual offsets against flush faces.
- **The checkout moved while I worked:** `levels/level1` left `worlds.txt` mid-build.
- **Earlier passes:**
  - the lid over the big tank is a dark mass, since the game's void is dithered;
  - the floor is painted from the lights, because corners cannot carry the shimmer;
  - refinement on glass was wasted, so the tanks bake corners only.
