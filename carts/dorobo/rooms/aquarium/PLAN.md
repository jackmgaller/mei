# Room 5: the aquarium (floor plan)

Level 1's last room (`levels/level1/ROUTE.md`), on the roof of the office tower: the sketch's
aquarium after closing, reached by the lift from the lobby. It is the level's reward and its
hardest room: it teaches nothing new but combines the four ideas before it, with one more,
glass: the jellyfish column and the coral cube let cones through but not the thief.

This folder is the aquarium builder's (`make_aquarium.py`, `capture.py`, the recipes and art).
This plan is the level lead's; the room's play file (its entities and wall map) is
`carts/dorobo/levels/level1/aquarium/aquarium.play.json`, written by `make_aquarium_play.py` there
from the numbers below.

## The plan

The sketch's frame and numbers, unchanged but for the two changes marked **Change**: x right, z
away from the camera, the floor y = 0, the origin in the middle of the floor. Metres.

```
 z 4.85 ┌───────────── the big tank (behind the window wall) ─────────────┐
   2.9  ├─ pier ─┬──────────── ocean window (glass) ────────────┬─ pier ──┤ staff door ▯ x 5.25 (the exit)
   2.42 │        ·  ·  ·  ·  stanchions (low)  ·  ·  ·  ·  ·              │
   2.0  │                 watchman ◆ (0, 2.0)                             │
   1.35 │                 ═══ bench (2.6 m) ═══     keeper's loop ┌──────┐│
        │   ◎ jellyfish (−2.9, −0.2)                            │ ▢cube ││ (3.0, 0.15), glass
        │     glass, r 0.75     ▫ sign (−1.65, −0.5)            └──────┘│
        │                  ▣ pillar (−0.2, −1.6)                  cart ▭ │ (4.7, −2.25)
  −2.9  ├─ front ─┤ way in ├──────── front wall, cut at 1 m ────────────────┤
        └ x −6.05 … 6.05 ── the way in: x −4.9 … −3.7 (from the lift) ─────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −5.8 … 5.8, z −2.9 … 2.9 | 11.6 × 5.8 | |
| Front wall | z −3.15 … −2.9, **cut at 1 m**, the way in at x −4.9 … −3.7 | | wall |
| Side walls | x ±5.8 … ±6.05 | full height | walls |
| Window wall | z 2.9 … 3.15 | piers, sill, glass | blocks the thief; cones go through the glass into the tank, where nobody stands |
| Jellyfish column | (−2.9, −0.2), r 0.75 | glass | stops the thief, **cones pass** |
| Coral cube | (3.0, 0.15), 1.42 square | glass | stops the thief, **cones pass** |
| Pillar | (−0.2, −1.6), 0.5 square | **Change: cut at 1 m** (the sketch's is 3.16 m) | **blocks cones**: its shadow is part of the solution |
| Bench | (0, 1.35) | **Change: 2.6 m long** (the sketch's is 3.4), 0.5 deep, low | stops the thief, cones pass. Shortened so the keeper can walk between it and the cube (the gap is 1 m) |
| Stanchions and rope | z 2.42, x −3.65 … 3.65 | low | stop the thief, cones pass |
| Jellyfish sign | (−1.65, −0.5) | low (under 1.5 m) | stops the thief, cones pass |
| Cleaner's cart | (4.7, −2.25), 0.9 × 0.5 | under 1 m | stops the thief, cones pass |
| Spawn | (−4.3, −2.45), facing the window | | in the way in |
| Exit | the staff door: (5.25, 2.6) | 0.8 × 0.6 | |
| Watchman (posted) | (0, 2.0), between the bench and the rope | 5 m, 60° | looks at the fish (0°: his cone through the window) 2.5 s, turns round (via the east, 1.5 s) to look over the room (180°) 2.5 s, turns back |
| Keeper (patrol) | round the cube: (4.9, −1.25), (4.9, 1.95), (1.75, 1.95), (1.75, −1.25) | 0.9 m/s, 4.5 m, 60°, head 180°/s | 1 s looks at the east and west corners |

The solution: along the front to x −2 (out of both guards' sight); when the watchman looks at the
fish, on to the pillar's shadow at (−0.2, −2.45); when he looks at the fish again and the keeper
is on the cube's far side walking west, along the front, up the east wall and through the staff
door. The tempting move, to hide behind the jellyfish column or the cube, fails: the cones go
through them.

## Must stay

- The positions and footprints above of the jellyfish column, the cube, the pillar, the bench, the
  rope, the cart and the sign, and which of them block cones (only the pillar and the walls).
  Glass must stay glass: nothing opaque inside or around the column and the cube's footprints.
- The way in at the front-left, the staff door at the back-right, the floor open along the keeper's
  loop and the watchman's spot.
- The front wall and the pillar cut at 1 m. The side and window walls may stay full height (they
  hide nothing that plays).
- If a number above must change, tell the level lead first: the wall map and the solution are
  written from these numbers.

## How the room joins the level

- **Recipes** stay in this folder; the level reads it (`make_level1.py` lists it in `ROOMS`).
  Names start `aq_` (the stand-ins and the cone here, `standin_*` and `sight_cone`, are not placed;
  keep their names off the other rooms' prefixes). Built in the frame above (origin in the
  middle of the floor), placed at yaw 0, the floor at y = 0. Verification required in depth mode,
  as now. Point lights and textures as you have them: the room is its own region in the level, so
  its textures are loaded only here (61 KB today; the region's budget is the default).
- **Placements**: write `aquarium.placements.json` here (format `after-hours-placements`, version 1,
  `room: "aquarium"`, `placements`: `id` (prefix `r5_`), `asset`, `position`, `collision`), and the
  level uses it. Until it exists the level places `aq_room` and `aq_tanks` at the origin.
- **Collision**: the level uses `aq_col` (floors and walls without tops, from this plan's numbers;
  `levels/level1/aquarium/collision/`) for `aq_room` and none for `aq_tanks`. If you split or move
  walls, give the room shell a collision companion of your own (walls without tops, so the World
  Checker finds no edge mismatches) or tell the lead.
- **Budget**: 2,500 triangles for the room (DESIGN.md); the sketch's two recipes are 1,655 as
  placed today. The kit makes the room's stand-in for the pull-back from the placements (capped
  at 800 triangles).
- **Checks**: `make B=build-mine build-mine/carts/dorobo.mei` builds the level with the World
  Checker; `python3 carts/dorobo/levels/level1/solutions.py --check` plays the solution on the
  model; the cart's scenario for the room plays the tape.
- **The tank's open top** (DESIGN.md, Gate 0: it reads as a second window) is yours to fix; the
  tank behind the window wall is out of play, so anything there is free.
