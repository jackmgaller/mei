# The station, room 2: the ticket gates (floor plan)

The station's second room (`levels/station/ROUTE.md`; until 2026-10-15 level 1's second). The
concourse at the top of the platform's stair, two floors underground: a line of automatic ticket
gates across it, the station office with its lit window at the back, a bank of coin lockers, ticket
machines, and on the far side of the gates the way up to the passage. One station guard comes out
of the office on his round: through the gates, a look down the stair, a look at the lockers, back
through the gates and a pause at the office door. It teaches hiding: the lockers have a gap the
thief can tuck into (A). Lit by the office window's warm light, the gates' small green and red
lamps, the machines' glow.

The greybox is `make_gates.py` (it writes `greybox/`, `gates.placements.json` and
`gates.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 4.5 ┌─────────────────────────── back wall (2.4 m) ───────────────────────────┐
   4.25│ lockers ███████[alcove]███████     ┌── office ──┐                         │
   3.35│ x −6.5 … −2.6  (−5.0 … −4.0)       │   desk     │                         │
   2.15│                                    └─window─door┘ ◆ office stop (0.95, 1.75)
   1.1 │                                         ║ barrier (glass over a low wall)  │
       │                                         ▪ gate   z 0.95                  │
       │          ◆ round: (−3.2, 2.3) lockers   ▪ gate   z −0.25   aisle z 0.35 ──┤
       │                                         ▪ gate   z −1.45                  │
       │ ┌stairwell┐  spawn ● (−3.6, −2.9)      ▪ gate   z −2.65   aisle z −2.05  ▯ exit (6.2, −2.6)
       │ │ (hole)  │  machines                   ▪ gate   z −3.85                ║ way up, z −3.6 … −1.6
  −4.25├─┴─────────┴──███──── front wall, cut at 1 m ─────────────────────────────┤
  −4.5 └ x −6.75 … 6.75 ─────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −6.5 … 6.5, z −4.25 … 4.25 | 13 × 8.5 | |
| Back wall, end walls | z 4.25 … 4.5; x ±6.5 … ±6.75 | 2.4 high | walls; the east wall has the way up at z −3.6 … −1.6 |
| Front wall | z −4.5 … −4.25 | **cut at 1 m** | wall |
| Gate line | x −0.3 … 0.3; cabinets 0.25 deep centred at z −3.85, −2.65, −1.45, −0.25, 0.95 | 1 m high | stop the thief, cones pass over; aisles 0.95 m between them |
| Barrier | x −0.3 … 0.3, z 1.075 … 2.15 | low wall and glass | stops the thief, cones pass |
| Office | x −1.6 … 1.6, z 2.15 … 4.25; walls 0.15 | **cut at 1 m** | side walls and the door jamb block cones; the window (x −1.45 … 0.6) is glass; door x 0.6 … 1.3 |
| Lockers | x −6.5 … −2.6, z 3.35 … 4.25, 2 m high | against the back wall | block cones |
| Hiding place | the lockers' gap, x −5.0 … −4.0, z 3.35 … 4.25 | 1 × 0.9 | `r2_hide_lockers`: A there hides him |
| Stairwell (from the platform) | x −6.5 … −4.3, z −4.25 … −1.6 | a railed hole | stops the thief, cones pass |
| Ticket machines | x −3.2 … −1.4, z −4.25 … −3.75 | under 1 m | stop the thief, cones pass |
| Spawn | (−3.6, −2.9), facing east | | the stair's head |
| Exit | (6.2, −2.6) | 0.6 × 2.0 | the way up to the passage |
| Guard (patrol) | starts (2.4, 0.4) | 0.9 m/s, 4.5 m, 60°, head 180°/s | (2.4, −2.05) → west through the aisle at z −2.05 → (−2.6, −2.05), looks at the stair 0.5 s → (−3.2, 2.3), looks at the lockers 1.5 s → (−2.6, 0.35) → east through the aisle at z 0.35 → (2.4, 0.35) → the office door (0.95, 1.75), looks out 2 s → round again |

The solution: into the lockers' gap and hide before he comes through the gates; when he has
looked at the lockers and is walking back east, out, south, through the front aisle (z −2.05) and
east to the way up.

## Must stay

- The gate line where it is and its aisles at z −2.05 and z 0.35 open (his route uses both), the
  barrier closing the line up to the office, and the gates low (cones must pass over them).
- The lockers' gap (the hiding place) and the lockers either side of it, tall: they are what
  makes the gap a hiding place he walks past.
- The office where it is, its door on the gate side; its window glass.
- The spawn, the exit and the stairwell; no cone-blocking thing between the gap and the front
  aisle, nor in the aisles.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The office (its desk, a fare-adjustment window, posters, a lit sign over it as a pictogram), the
gates' lamps and their arrows, the fare map over the machines (lit shapes, not words), the
lockers' doors and numbers as texture, a clock, the floor's tactile lines, the stair's rail and
the light coming up it, the way up to the passage beyond the east wall.

## Rules for every room

As room 1's PLAN.md ("Rules for every room"), with this room's prefix `r2_` and its placements
in `gates.placements.json`: the 1 m cut, 2,500 triangles for the room (the greybox is about 200),
recipes verified in depth mode, a collision companion (floors, walls without tops) for every
placement that needs one.
