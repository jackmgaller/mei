# Room 3: the passage (floor plan)

Level 1's third room (`levels/level1/ROUTE.md`). A long tiled passage under the street, one floor
down: its little shops' shutters down along the back wall, a vending machine glowing at the front,
square pillars staggered down its length. A security camera high on the far end wall sweeps the
whole passage, slowly. It teaches that pillars cast sight shadows: go from one shadow to the next
as the sweep passes. Lit by the vending machine, the shutters' small lamps and the tunnel lights,
with the camera's red lamp at the end.

The greybox is `make_passage.py` (it writes `greybox/`, `passage.placements.json` and
`passage.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. The passage is 22 m long: wider than a screen, so the camera pans.

```
 z 3.65 ┌───────────────── back wall (2.4 m): shutters x −9.5…−5.5, −4.5…−0.5, 0.5…4.5 ─────────────┐ camera ◉
   3.4  │                                                                                          │ (10.85, 2.9),
 entry  │        ▣ (−6.5, 0.6)                     ▣ (1.5, 0.6)                                    │ 2.3 m up
 z −0.6 ║                                                                                          │
 …−2.6  ║ spawn ●            ▣ (−2.5, −1.4)                          ▣ (5.5, −1.4)               ▯ exit (10.7, −2.5)
  −3.4  ├────────────────────────────── vending ███ (−0.6 … 0.6) ── front wall, cut at 1 m ─────────║ way on, z −3.4 … −1.6
  −3.65 └ x −11.25 … 11.25 ───────────────────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −11 … 11, z −3.4 … 3.4 | 22 × 6.8 | |
| Back wall | z 3.4 … 3.65, with three shop fronts (shutters) | 2.4 high | wall |
| Front wall | z −3.65 … −3.4 | **cut at 1 m** | wall |
| West wall | x −11.25 … −11, the way in at z −2.6 … −0.6 | 2.4 high | wall |
| East wall | x 11 … 11.25 from z −1.6 back; the way on at z −3.4 … −1.6 | 2.4 high | wall |
| Pillars | (−6.5, 0.6), (−2.5, −1.4), (1.5, 0.6), (5.5, −1.4) | 0.8 square, **cut at 1 m** | block cones: their shadows are the puzzle |
| Vending machine | x −0.6 … 0.6, z −3.4 … −2.9 | under 1 m | blocks cones |
| Camera | (10.85, 2.9), 2.3 m up on the east wall | | sweeps 235° ↔ 285° (along the front ↔ along the back), holds 1 s at each end, 3.5 s each turn; 13 m, 34° |
| Spawn | (−10.4, −1.6), facing east | | |
| Exit | (10.7, −2.5) | 0.6 × 1.8 | the way on, under the camera |

The solution: along the front to x −3 (beyond the camera's reach); when it sweeps along the back,
on to the shadow of the pillar at (5.5, −1.4), standing at (4.6, −2.3); when it sweeps along the
back again, on to the door. The west half of the passage is out of its reach: a safe place to
watch the sweep first.

## Must stay

- The camera where it is, and the pillars where they are and opaque: their shadows, seen from
  the camera, are the solution. A pillar may get thicker (not thinner) and keep its centre.
- Nothing else that blocks cones in the east half (x > −2) beyond the pillars and the vending
  machine; low things (benches, bins under 1 m) are fine if they do not stop the thief on the
  front strip (z −3.4 … −1.8) or between the last pillar and the door.
- The exit under the camera, at the front of the east wall.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The shops' shutters and their signs (lit shapes), the tiles and their pattern, a poster wall,
the vending machine's light painted on the floor, ceiling lamps as pools of light, the stairs
beyond both doors, a lost umbrella. The camera's body is drawn by the game (agent A).

## Rules for every room

As room 1's PLAN.md ("Rules for every room"), with this room's prefix `r3_` and its placements
in `passage.placements.json`: the 1 m cut, 2,500 triangles for the room (the greybox is about 140),
recipes verified in depth mode, a collision companion for every placement that needs one.
