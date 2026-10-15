# Room 4: the lobby (floor plan)

Level 1's fourth room (`levels/level1/ROUTE.md`). The ground-floor lobby of the office tower above
the passage, at night: a stone floor, a reception desk in the middle, two big planters, the lifts
shut for the night in the east wall, and a stopped escalator rising along the back wall: the only
way up. Two night guards walk lines that cross: one up and down the west side from the passage's
door to the back, one along the back in front of the escalator. It teaches two routes crossing:
get past one, then wait for the other. Lit by the street through the glass front (cut away: the
light painted on the floor), the desk's lamp, the lifts' lit call buttons.

The greybox is `make_lobby.py` (it writes `greybox/`, `lobby.placements.json` and
`lobby.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 5.0  ┌──────────────────────────── back wall (2.4 m) ──────────────────────────────┐
   4.75 │                              ▯ exit (0.55, 4.12) ═══ escalator ↗ x 1 … 7 ═══╡ rises east
   3.5  │                      ── back guard ◆ x −2.6 … 3.8 at z 2.6 ──  balustrade  │
        │   west guard ◆                                                              │
        │   x −3.2,          ▣ planter (−5.4, 0.6)                                    ║ lifts (z −1 … 1)
        │   z −3.8 … 3.6        ┌──── desk x −1.6 … 1.6, z −0.5 … 0.4 ────┐           │
        │                                                     ▣ planter (3.6, −2.2)  │
 entry  ║ spawn ● (−6.4, −3.7)                                                        │
  −4.75 ├────────────────────────── front wall, cut at 1 m ──────────────────────────┤
  −5.0  └ x −7.25 … 7.25 ───────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −7 … 7, z −4.75 … 4.75 | 14 × 9.5 | |
| Back wall, east wall | z 4.75 … 5.0; x 7 … 7.25 | 2.4 high | walls; the lifts are in the east wall (z −1 … 1) |
| West wall | x −7.25 … −7, the way in at z −4.5 … −2.9 | 2.4 high | wall |
| Front wall | z −5.0 … −4.75 | **cut at 1 m** | wall (the glass front, in the story) |
| Desk | x −1.6 … 1.6, z −0.5 … 0.4 | **cut at 1 m** | blocks cones (a counter with screens) |
| Planters | (−5.4, 0.6), (3.6, −2.2) | 1 m square, **cut at 1 m** | block cones |
| Escalator | its foot at x 1.0, up to the east wall; z 3.5 … 4.75 | rises 2.3 m, 12 steps | out of bounds above its foot; its balustrade (z 3.5 … 3.63) blocks cones |
| Exit | the escalator's foot, (0.55, 4.12) | 0.7 × 1.1 | the way up |
| Spawn | (−6.4, −3.7), facing east | | the passage's door |
| West guard (patrol) | (−3.2, 0.4) | 0.8 m/s, 4.5 m, 60°, head 180°/s | south to (−3.2, −3.8), looks at the front 1 s; north to (−3.2, 3.6), looks at the back 1 s; again |
| Back guard (patrol) | (3.8, 2.6) | the same | west to (−2.6, 2.6), looks west 2 s; east to (3.8, 2.6), looks east 2 s; again |

The solution: wait at the door until the west guard has turned back north; cross behind him to
the desk's east side (2.2, −1.1); when the back guard is at an end of his walk, looking away, round
the desk and up to the escalator's foot.

## Must stay

- The escalator and its foot (the exit) at the back, the back guard's line in front of it, the
  west guard's line down the west side, and the spawn by the passage's door.
- The desk where it is and opaque: the thief waits behind it, out of both guards' sight.
- Open floor along both guards' lines and between the desk and the escalator's foot; nothing
  that blocks cones between the back guard's line and the escalator's foot (the puzzle is seeing
  him and being seen by him).
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The desk (a lamp, a signing-in book, the tower's name as a lit logo shape), the planters' plants
(cut at 1 m, or kept low), the lifts' doors and their lit numbers, the escalator's steps and
handrails, stone floor and the street light through the glass front painted on it, a directory
board (shapes, not words), a sofa (low).

## Rules for every room

As room 1's PLAN.md ("Rules for every room"), with this room's prefix `r4_` and its placements
in `lobby.placements.json`: the 1 m cut, 2,500 triangles for the room (the greybox is about 200),
recipes verified in depth mode, a collision companion for every placement that needs one.
