# Aquarium room: notes

Level 1's last room, on the roof of the office tower: the aquarium after closing, lit only by its
tanks. The ocean window runs across the back wall, with a turtle, a ray, a shark, a silver school,
rock, kelp and light shafts. There is a violet jellyfish column, a teal coral cube, small tanks set
into the side walls, cyan guide lights in the floor, a bench, stanchions, a structural pillar, a
night cleaner's cart and the staff door at the back right. The way in from the lift is at the
front left. The layout and the play are the level lead's, in `../PLAN.md`; this folder's recipes
follow it.

Shots:

| File | What |
|---|---|
| `aquarium_60.png` | The game's own camera, as `dr_view.akr` frames the room (20° lens, 28.166 m, the room's front edge on line 246), drawn by `capture.py` |
| `aquarium_level_60.png` | The room in the built level: scenario 45 (the room's solution tape) at tick 500, the game's HUD included |
| `aquarium_45.png`, `aquarium_75.png` | Each pitch framed so the floor's front edge spans the picture, the room centred |
| `aquarium_*_x3.png` | The same, scaled up three times pixel for pixel |
| `compare.png` | 45°, 60° and 75° side by side |
| `relight_60.png` | The sketch, the trial relight and the room now, side by side |

`capture.py`'s stand-ins show one moment of PLAN.md's solution. The watchman (0, 2.0) looks over
the room with a 5 m cone, and the thief stands in the pillar's sight shadow at (−0.22, −2.5). The
keeper walks west along the cube's far side with a 4.5 m cone. `numbers.json` has every figure
below.

## How it is made

- `../make_aquarium.py` writes the recipes beside it, `../aquarium.placements.json` and
  `../art/*.png`. It needs Pillow and NumPy; text uses Figtree and Zen Maru Gothic from
  `tools/fonts/`.
- `../capture.py --verify` runs the Asset Checker on every recipe, packs them, draws each view
  with `mei-headless` into `build-dorobo-sketch/dorobo/aquarium/`, and writes the shots and
  `numbers.json`. It takes about 20 s.
- To check the room in the level (`make` builds it with the World Checker, the other two lines
  play the room's tape, the last one draws `aquarium_level_60.png`'s frame):

  ```
  make B=build-dorobo-sketch build-dorobo-sketch/carts/dorobo.mei
  python3 carts/dorobo/levels/level1/solutions.py --check
  MEIC=$PWD/build-dorobo-sketch/meic RUN=$PWD/build-dorobo-sketch/mei-headless \
    WORLDS=$PWD/build-dorobo-sketch/cart-worlds/dorobo carts/dorobo/tests/run.sh 45 1000 OUT
  SHOT=1 SEQ=100   # with the run.sh line above: no test overlay, and every 100th frame saved
  ```

- **Light.** `room_lights()` holds 12 point lights:
  - the window (4, with soft shadows);
  - the jellyfish column, the coral cube and the lift at the way in (soft shadows);
  - the exit sign;
  - the 4 small wall tanks.

  The Asset Kit bakes these lights into the walls and props, with at most 160 refinement
  triangles. `paint_floor()` paints the emissive floor from the same lights and adds what corners
  cannot carry: the water's shimmer, soft shadows, the guide studs and a glow round the coral
  cube's pedestal. The tanks' recipe has two lights of its own, corners only.

| Recipe | Triangles | Vertices | |
|---|---|---|---|
| `aq_room` | 640 | 440 | placed by the level as `r5_room_shell`, with the level lead's collision `aq_col` |
| `aq_tanks` | 1,017 | 945 | placed as `r5_tanks`, no collision |
| **room** | **1,657** | | of PLAN.md's 2,500; the World Checker's stand-in for the pull-back is 640 (of 800) |
| `standin_thief`, `standin_guard`, `sight_cone` | 116, 168, 32 | | for `capture.py` only; the level does not place them |

All five recipes pass the Asset Checker in depth mode. Textures take 61,009 bytes of VRAM.

## Changes for PLAN.md and the coordinator's notes (2026-10-15)

- **Pillar** cut at 1 m with a cut top (it was 3.16 m). It still blocks cones.
- **Bench** shortened to 2.6 m.
- **Footprints brought inside the plan's** so that nothing drawn stands where the thief can walk:
  - the jellyfish plinth r 0.86 → 0.76 and its rim 0.88 → 0.77 (the glass is r 0.75);
  - the cube's pedestal 1.5 → 1.48 m square (the glass is 1.42);
  - the sign's panel 0.62 → 0.44 m wide (its wall is 0.4 × 0.2);
  - the mop moved onto the cart's 0.9 × 0.5 footprint.
- **The section's cut tops** darkened from `#76849e` to `#3c475e`.
- **The coral cube's teal pool** painted back: a glow round the pedestal in the floor's texture,
  since the window's cyan swamps what the cube's point light gives there.
- **The way in** is from the lift now. The lanterns' amber light became a warm white from the
  lift.
- **The tank's lid** is a dark mass (`#121826`, emissive) instead of the void's colour. The game's
  void (`dr_view.akr`, rgb(6, 10, 22)) is drawn dithered between two colours, so no flat lid can
  match it, and the void may later become a night sky. As a dark building beyond the room, the lid
  reads the same either way.
- **`aquarium.placements.json`** is now in this folder, with the same placements the level lead
  had: `r5_room_shell` (`aq_room`, collision `aq_col`) and `r5_tanks` (`aq_tanks`, none).

**Against the level lead's files** (`levels/level1/aquarium/`, not changed): the walls, glass,
pillar, bench, rope, cart and sign match `aquarium.play.json`'s wall map and `aq_col`. The floor
slab is drawn 3 cm larger than `aq_col`'s floor, for the section's edge; that is not a mismatch
for play.

## In the level

- `make B=build-dorobo-sketch build-dorobo-sketch/carts/dorobo.mei` builds, with the World
  Checker reporting 0 hard failures and 0 over thresholds.
- The aquarium cell has 1,657 triangles (limit 2,500), 2 placements, and a stand-in of 640.
- At the game's camera the World Checker draws 898 triangles, 201,233 draw-CPU and 154,421 GPU
  cycles, without entities.
- `solutions.py --check`: the aquarium is cleared at 768.
- Scenarios 41–45 (each of level 1's room tapes, played in the built level) all end DONE; 45 is
  this room, cleared on tick 770. They are not in `tests/check.sh` yet.
- Scenario 45 as a release build (`TRAP=0`), measured over the tape (ticks 5–760): CPU
  262,565–280,722 cycles, GPU 361,487–383,710, 1,238–1,254 triangles a frame.

## Costs in `capture.py`, per frame

The budgets are 1,000,000 CPU and 2,000,000 GPU cycles. These frames have the room, the thief,
two guards and their cones (the relight's shots had one guard). The 60° view is now the game's
framing, which is closer than the relight's 60° shot.

| Pitch | px per m | Thief (rows / a 1.7 m vertical) | Triangles drawn | CPU cycles | GPU cycles |
|---|---|---|---|---|---|
| 45° | 23.4 | 32 / 28.3 px | 1,288 | 259,713 (26 %) | 358,686 (17.9 %) |
| 60° | 24.2 | 22 / 16.7 px | 1,286 | 259,610 (26 %) | 381,779 (19.1 %) |
| 75° | 25.1 | 14 / 7.1 px | 1,249 | 256,089 (26 %) | 373,938 (18.7 %) |

At 60° in the game's framing the thief, in the pillar's shadow at z −2.5, stands at the foot of
the picture with his legs below its edge. His 22 rows are what shows.

- **With a third guard and the cones drawn twice:** 276,928–281,624 CPU, 380,282–409,342 GPU and
  1,351–1,402 triangles drawn.
- **The glass:** the window, the column's and cube's glass, and their water surfaces, 58
  triangles. It costs 25,813–32,097 GPU cycles (1.3–1.6 % of the GPU budget) and about 24,600
  CPU cycles. Everything semi-transparent costs 61,870–67,085 GPU cycles.

**Over time**, with the same figures as before:

| | Room triangles | CPU at 60° | GPU at 60° |
|---|---|---|---|
| The sketch | 1,493 | 221,559 | 362,897 |
| The trial relight (point lights, defaults) | 2,025 | 301,251 | 404,646 |
| The relight | 1,655 | 238,879 | 353,428 |
| Now (two guards, the game's framing) | 1,657 | 259,610 | 381,779 |

The rows are not all the same scene. The sketch and the relight drew one guard and one cone in a
looser framing; "now" draws two of each in the game's framing. The room's own change since the
relight is two triangles. The rest is the second guard and cone (about 200 triangles and 20,000
CPU cycles) and the closer framing.

## What fought me

- **The level's void cannot be matched by a flat face.** `cls` dithers rgb(6, 10, 22) between two
  15-bit colours, so the lid became a dark mass instead.
- **`capture.py` had to learn the game's framing** (`frame_room()` in `dr_view.akr`). Its fitted
  60° view showed the room smaller than the game does, and the comparison only means something in
  the game's frame.
- **The two stand-in fans** lay in one plane where they overlap, which the Asset Checker fails as
  a coplanar overlap. They are now 1 cm apart.
- **From the relight:**
  - refinement split glass it lit, for nothing, so the window glass moved to the tanks' recipe and
    the tanks bake corners only;
  - a point-lit floor loses the shimmer, so the floor is painted from the lights;
  - the cut faces had to be emissive, since the lights stand below them;
  - lights reach only their own recipe.
- **From the sketch:**
  - every wall junction needed a 1–4 cm offset to pass the Asset Checker;
  - the kit's camera preview draws one asset at 60°, so `capture.py` writes its own carts;
  - text 0.36 m tall does not read at this scale.

## For the level lead

- At the game's framing, the front row of the floor (the spawn at z −2.45, the pillar's shadow at
  −2.5) sits at the foot of the screen, and a thief there shows only from the waist up. The plan
  is not wrong; it is what that framing does.
- The way in has nothing beyond it but the void (the wall map's `r5_wall_entry_beyond` is not
  drawn). If the lift should be seen, it is a small addition here.
