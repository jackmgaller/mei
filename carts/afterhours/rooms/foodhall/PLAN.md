# The department store (stage 3), room 4: the food hall (floor plan)

The store's last room (`levels/store/ROUTE.md`). The department store's basement, the depachika:
two rows of lit cases (cakes, fruit, wrapped boxes) either side of a middle aisle, the melon
counter at the east end, columns, stacks of gift boxes. The service lift from the shop floor opens
in the back wall at the west end; the way out, to the underground mall (stage 3's way home), is the
shutter door at the front of the east wall. A cleaner pushes his cart round all the cases; the
guard at the melon counter looks along the hall from side to side; a camera on the back wall sweeps
the middle. A stack of gift boxes brushed falls with a noise that brings the guards to look.

The greybox is `make_foodhall.py` (it writes `greybox/`, `foodhall.placements.json` and
`foodhall.play.json`). The dressed room replaces the greybox recipes and the placements file;
the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 5.0  ┌─[lift]──────────────── back wall (2.4 m) ── ● camera (0, 4.6) ─────────────────┐
   4.75 │ x −10.4 … −9.0                                         ▪ column (4.25, 3.4)        │
        │ ● spawn (−9.7, 3.75)   ◆ cleaner NW (−8.6, 2.9)   ◆ cleaner NE (8.4, 2.9)          │
        │        ┌─cases─────────┐       ┌─cases─────────┐   ┌melon┐                       │
        │        │x −7.5 … −1    │       │x 1 … 7.5      │   │count│ ◆ guard (11, 0.6)      │
        │        └───────────────┘ ▣gifts└───────────────┘   │x 9.6│   looks 200 … 300     │
        │ ▣ gifts (−9, −2.2)       (−1.7, 0.05)              │…10.4│                       │
        │        ┌─cases─────────┐       ┌─cases─────────┐   └─────┘                       │
        │        └───────────────┘       └───────────────┘                    ▣ gifts (8.6, −3.4)
        │ ◆ cleaner SW  ▪ column (−4.25, −3.6)          ◆ cleaner SE (8.4, −2.6)            ▯ way out
 −4.75  ├──────────────────────── front wall, cut at 1 m ─────────────────────────────────┤ z −3.6 … −2.4
 −5.0   └ x −12.25 … 12.25 ────────────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −12 … 12, z −4.75 … 4.75 | 24 × 9.5 | |
| Back wall, end walls | z 4.75 … 5.0; x ±12 … ±12.25 | 2.4 high | walls; doorways: back x −10.4 … −9.0 (the lift), east z −3.6 … −2.4 (the way out) |
| Front wall | z −5.0 … −4.75 | **cut at 1 m** | wall |
| Cases | x −7.5 … −1.0 and 1.0 … 7.5, at z −1.7 … −1.0 and 1.1 … 1.8 | 0.95 | glass: stop the thief, cones pass |
| Melon counter | x 9.6 … 10.4, z −1.0 … 2.4 | 0.9 | stops the thief, cones pass |
| Columns | (−4.25, −3.6) and (4.25, 3.4), 0.7 square | to the ceiling (cut at 1 m) | block cones: the west one is where he waits |
| Gift boxes | (−1.7, 0.05), (8.6, −3.4), (−9.0, −2.2), 0.4 m round | | `fragile`, noise 8 m: brushing one knocks it down and brings the guards; the one at (8.6, −3.4) is on the natural way to the door |
| Lift door | back wall, `fh_door_lift` | 1.4 wide | to `sf_door_lift` (the way back up); spawn (−9.7, 3.75) facing south |
| Way out | east, `fh_door_mall`, `end` | 1.2 wide | the stage's end; not a way in |
| Cleaner (patrol) | starts (2.0, −2.6) | 1.0 m/s, 4.5 m, 60°, head 200°/s | east along the front → (8.4, −2.6) → (8.4, 2.9) looks west 1 s → along the back → (−8.6, 2.9) → (−8.6, −2.6) → round again (about 46 s) |
| Melon counter guard (posted) | (11.0, 0.6) | 6 m, 60° | looks 200 (down the front aisle) 2 s, turns to 300 (up the hall) over 2.5 s, holds 2 s, turns back: 540 ticks a cycle |
| Camera | (0, 4.6), 2.3 up | 7 m, 36° | sweeps 150 … 210 over the middle (holds 1.5 s, turns 2 s) |

The solution (`SOLUTION_S2_LEG_7`): down the west end, round the gift boxes there, to the west
column at the front; when the melon counter guard has turned to look up the hall (the clock 620,
one of three windows about 3 s wide before the cleaner comes round), along the front aisle, round
the stack of gift boxes by the door, and out. About 17 s.

## Must stay

- The cases' two rows, glass and low, and the aisles between them; the melon counter low.
- The two columns, blocking cones; the west one at the front.
- The gift boxes where they are, with room to walk round each (0.4 m round; the thief's footprint
  is 0.3).
- The doorways, the lift's spawn, the guard's place at the melon counter, the camera's place.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The cases' contents lit from inside (cakes in rows, melons in boxes, wagashi, fruit pyramids),
price cards as colours, noren over the counters, paper lanterns, the cleaner's cart (drawn by
the room, the cleaner by A), the shutter door half up with the mall's light under it, the lift's
open car beyond the back wall.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `fh_` and its
placements in `foodhall.placements.json`.
