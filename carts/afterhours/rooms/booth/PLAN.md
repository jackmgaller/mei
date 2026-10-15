# Stage 2, room 1: the projection booth (floor plan)

Stage 2's dead end with the red card (`levels/level2/ROUTE.md`). Up the stair behind the staff
corridor's blue door: a long, low room over the back of the cinema, its two projectors running
the last reel through the ports in the west wall (their beams out into the dark auditorium), the
rewind bench along the back wall, racks of film cans. The projectionist walks round his west
machine and stops between the two to watch the east one. The **red card** (the service lift's
key) lies at the far end of the bench. In and out by the same door: the quiet room of the stage.

The greybox is `make_booth.py` (it writes `greybox/`, `booth.placements.json` and
`booth.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 3.25 ┌──────────────── back wall (2.4 m) ─────────────────────────┐
   3.0  │ rewind bench (low) x −5.6 … −1.8   │ film racks (tall)     │
        │ ▬ red card (−5.0, 1.9)             │ x 2.0 … 4.6           │
        │ ◆ C (−5.0, 1.6) ──────────────▶ ◆ D (−1.8, 1.6)            │
  ports │      ┌─proj 0─┐                 ┌─proj 1─┐                 │
 (west  │  ▲   │x −3.9… │       ▼         │x 0.1…  │                 │
  wall) │  │   │  −3.1  │                 │  0.9   │                 │
        │ ◆ B (−5.0, −1.4) ◀──────────── ◆ A (−1.8, −1.4) looks 55   ▯ door z −2.4 … −1.2
        │                                                      ● spawn (5.1, −1.8)
  −3.0  ├──────────── front wall, cut at 1 m ───────────────────────┤
 −3.25  └ x −6.25 … 6.25 ───────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −6 … 6, z −3 … 3 | 12 × 6 | |
| Back wall, end walls | z 3.0 … 3.25; x ±6 … ±6.25 | 2.4 high | walls; doorway: east z −2.4 … −1.2 |
| Front wall | z −3.25 … −3.0 | **cut at 1 m** | wall |
| Projectors | x −3.9 … −3.1 and 0.1 … 0.9, z −0.4 … 1.0 | 1.6 high (cut at 1 m) | block cones and the thief: the shadows he hides in |
| Rewind bench | x −5.6 … −1.8, z 2.4 … 3.0 | 0.9 | stops the thief, cones pass |
| Film racks | x 2.0 … 4.6, z 2.1 … 3.0 | 2.0 high, against the back wall | block cones |
| Ports | the west wall, z −0.2 … 1.4 | | drawn only: the projectors face them |
| Red card | (−5.0, 1.9) | | `pb_card_red`: drawn by A |
| Door | east, `pb_door_corridor` | 1.2 wide | to `sc_door_booth`; spawn (5.1, −1.8) facing west |
| Projectionist (patrol) | starts at A (−1.8, −1.4) | 1.0 m/s, 5 m, 60°, head 220°/s | at A watches the east machine (55) 2 s → west along the front → B (−5.0, −1.4) → up the far end → C (−5.0, 1.6) → east along the bench → D (−1.8, 1.6) → down between the machines → A (about 14.5 s a round) |

The solution (`SOLUTION_S2_LEG_4`): wait by the door until he has gone up the far end; along
the front of the machines; up the far end behind him as he walks back along the bench, over the
card, and into the west machine's shadow (−4.6, 1.6); when he is walking down the front again,
back along the bench, down the east end and out. About 23 s.

## Must stay

- The two projectors where they are, blocking cones, with the lanes round them (the front
  z −3.0 … −0.4, the bench lane z 1.0 … 2.4, between them x −3.1 … 0.1, the far end x −6 … −3.9)
  free.
- The card's place at the bench's west end; the bench low.
- The doorway and its spawn; the racks against the back wall, not in the bench lane.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The projectors (big 35 mm machines, their lamp houses glowing, the film path, reels turning),
the beams through the ports, the rewind bench (a splicer, reels, cans), posters of old films as
shapes, a kettle, the stair beyond the door.

## Rules for every room

As `levels/level2/ROUTE.md`, "Rules for every room", with this room's prefix `pb_` and its
placements in `booth.placements.json`.
