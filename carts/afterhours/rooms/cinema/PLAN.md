# The department store (stage 3), room 0: the cinema (floor plan)

The store's first room (`levels/store/ROUTE.md`). An auditorium on the eighth floor of a department
store, after the last show: the screen still lit by the film running in the booth, the projector's
beam over the seats, the exit signs. The assessor comes in behind the screen by the cinema's
backstage door, off the store's goods lift (the stage's start; until the split it was the
aquarium's service corridor: the dressing beyond that doorway changes, nothing in play). An usher
walks round the seats with a torch; a cleaner works up and down one cross aisle; the projector's
window high in the east wall looks straight down the middle aisle and never moves. The way out is
the staff door at the back of the east wall, to the staff corridor.

The greybox is `make_cinema.py` (it writes `greybox/`, `cinema.placements.json` and
`cinema.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. North is the back wall.

```
 z 4.75 ┌──────────────────────────── back wall (2.4 m) ─────────────────────────────┐
   4.5  │ ░gap░│  back aisle (z 3.0 … 4.5)                            ◆ usher NE        ▯ staff door
        │      │ ┌seats 01┐   ┌seats 11┐ ◆ cleaner N ┌seats 21┐                     ║ z 2.6 … 3.8
        │ spawn│ │        │   │        │  (1.9, 3.75)│        │                     │
        │ ● ◀▯ │ └────────┘   └────────┘   cross     └────────┘    ◀═══ projector's │
  screen│door  │ ─── middle aisle (z −0.7 … 0.7) ─── aisle 2 ──────── window (10.85, 0)
 x −9.3 │ x−11 │ ┌seats 00┐   ┌seats 10┐   x 1.2…2.6 ┌seats 20┐     cone 10 m, 30°  │
 … −9.0 │      │ └────────┘   └────────┘             └────────┘                     │
        │      │ front aisle (z −4.5 … −3.0)   ◆ usher SW … SE ◆   ◆ cleaner S      │
  −4.5  ├──────┴──────────── front wall, cut at 1 m ─────────────────────────────────┤
 −4.75  └ x −11.25 … 11.25 ──────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −11 … 11, z −4.5 … 4.5 | 22 × 9 | |
| Back wall, end walls | z 4.5 … 4.75; x ±11 … ±11.25 | 2.4 high | walls; doorways: west z −0.6 … 0.6 (behind the screen), east z 2.6 … 3.8 |
| Front wall | z −4.75 … −4.5 | **cut at 1 m** | wall |
| Screen | x −9.3 … −9.0, z −3.2 … 3.6 | cut at 1 m like the play area (a wall to the cones whatever its drawn height) | blocks cones; the gaps round it, z −4.5 … −3.2 (front) and z 3.6 … 4.5 (back), are the ways out from behind it |
| Seats | three blocks x −7.0 … −3.6, −2.2 … 1.2, 2.6 … 6.0, each in two halves z −3.0 … −0.7 and 0.7 … 3.0 | 0.9 high | stop the thief, cones pass over (`cn_wall_seats_*`) |
| Aisles | front z −4.5 … −3.0; back z 3.0 … 4.5; middle z −0.7 … 0.7; cross x −3.6 … −2.2 and 1.2 … 2.6; the sides x −9.0 … −7.0 and 6.0 … 11.0 | | free |
| Start door | the west wall's doorway, `cn_door_screen` | 1.2 wide | the stage's start; not a way back (no `to`) |
| Spawn | (−10.2, 0), facing east | | behind the screen |
| Staff door | the east wall's doorway, `cn_door_corridor` | 1.2 wide | to the staff corridor (`sc_door_cinema`); its spawn (10.1, 3.2) facing west |
| Projector's window (camera) | (10.85, 0), 2.3 up | 10 m, 30°, fixed at 270 (west) | the beam: covers the middle aisle and the seats' middles east of x 1 |
| Usher (patrol) | starts (−8.0, 1.0) | 1.1 m/s, 5 m, 60°, head 200°/s | (−8.0, −3.75) looks east 0.5 s → along the front → (7.6, −3.75) looks north 1 s → (7.6, 3.75) → along the back → (−8.0, 3.75) → round again (about 48 s) |
| Cleaner (patrol) | starts (1.9, −3.0) | 0.9 m/s, 4.5 m, 60°, head 200°/s | up and down the second cross aisle: (1.9, −3.75) looks east 1.5 s, (1.9, 3.75) looks west along the back aisle 1.5 s |

The solution (`SOLUTION_S2_LEG_0`): wait behind the screen while the usher comes down the west
side; when he walks along the front, out of the back gap and along the back aisle to the first
cross aisle (x −3.6), out of the cleaner's reach; when the cleaner sets off back down his aisle,
along the back and up to the staff door before the usher comes up the east side. About 21 s.

## Must stay

- The screen where it is, with its two gaps (the back gap at least 0.9 m clear).
- The seats' blocks and every aisle as above, the seats low (cones pass over them).
- The projector's window over the middle aisle in the east wall: nothing that blocks cones in the
  middle aisle or between the seats' blocks.
- The doorways, the spawn, and nothing tall along the back aisle.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The screen (the film's light on it, flickering: a palette cycle or a texture), the curtains
either side, rows of seats as rows, the beam over the seats (light only, high), the exit signs
over the doors (pictograms), carpet, wall lamps, the space behind the screen (speakers, the
backstage door to the goods lift), the staff door's landing beyond the east wall.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `cn_` and its
placements in `cinema.placements.json`.
