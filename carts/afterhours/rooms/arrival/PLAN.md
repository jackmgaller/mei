# The station, room 1: the last train (floor plan)

The station's first room (`levels/station/ROUTE.md`; until 2026-10-15 level 1's first). The far end
of a side platform three floors under the complex, after midnight. The thief steps off the last
train, which pulls out behind him into the tunnel; the stair up to the ticket gates is at the
platform's east end, and a station guard stands beside it, looking up the platform, then turning to
the timetable. It teaches what a cone is, and timing one. It should be calm and lit by the
platform's fluorescent tubes, the train's lit windows sliding away, and the stair's light from
above.

The greybox is `make_arrival.py` (it writes `greybox/`, `arrival.placements.json` and
`arrival.play.json`). The dressed room replaces the greybox recipes and the placements file; the
play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, y up, the origin in the middle
of the floor; the platform's top is y = 0. Metres.

```
 z  3.75 ┌──────────────────────── back wall (2.4 m) ─────────────────────────┐ timetable (lit) at x 5
    3.5  │  track (bed y −1.1), the train runs +x, x −6.75 … 6.75 (tunnels)     │
    1.1  ├─ platform edge ───────────────────────────────────────────────────┤
         │  ▣ pillar (−5.0, −1.2)      spawn ● (−3.08, 0.6)          ┌stair──┐ │ stair up x 3.6 … 6.5,
         │                                                exit ▯ (3.2) │ ↗ ↗ ↗ │ │ z −1.3 … 0.9, 11 steps
         │      bench (−3.0, −2.6)   bench (0.4, −2.6)               └───────┘ │
         │                                                   guard ◆ (5.5, −3.2)
   −4.25 ├─ front wall, cut at 1 m ─────────────────────────────────────────┤
   −4.5  └ x −6.75 … 6.75 ─────────────────────────────────────────────────┘
```

| Thing | Where (x, z) | Size | In play |
|---|---|---|---|
| Platform | x −6.5 … 6.5, z −4.25 … 1.1 | 13 × 5.35 | the floor |
| Track | z 1.1 … 3.5, bed at y −1.1 | 2.4 wide | the train's band; out of bounds |
| Back wall | z 3.5 … 3.75 | 2.4 high | wall |
| Front wall | z −4.5 … −4.25 | **cut at 1 m** | wall |
| End walls | x ±6.5 … ±6.75 | 2.4 high, tunnel mouths over the track (to y 2.2) | wall |
| Stair up | x 3.6 … 6.5, z −1.3 … 0.9 | rises east to 2.2 m | wall, but for its foot (x 3.6 … 3.9) |
| Exit | the stair's foot, (3.2, −0.2) | 0.8 × 2.2 | the room clears here |
| Spawn | (−3.08, 0.6), facing the camera | | off the train's first door (x −3.33) |
| Pillar | (−5.0, −1.2) | 0.5 square, **cut at 1 m** | blocks cones |
| Benches | (−3.0, −2.6), (0.4, −2.6) | 1.8 × 0.45, 0.45 high | stop the thief; cones pass |
| Guard (posted) | (5.5, −3.2) | | looks 300° (up the platform) 4 s, turns 1.5 s, looks 165° (the timetable) 4 s, turns back; 5.5 m, 60° |
| Train | track, head stops at x 5.0 (doors at x −3.33, 0, 3.33) | 2 cars × 10 m × 2.4 m | drawn by the game; doors shut at clock 0, pulls out east over 6 s, does not return |

## Must stay

- The stair and the exit at the platform's east end, the guard beside it, and the sight line
  from him up the platform: nothing that blocks cones between x −1 and x 5.5 at the platform's
  back half (the solution waits at (−1.0, 0.3), just out of his reach, and walks to the stair's
  foot when he turns).
- The spawn in front of the train's first door, out of his reach.
- The front wall cut at 1 m; the track, the platform edge and the walls where they are (the wall
  map, `arrival.play.json`, is written from these numbers: a change there is the level lead's).
- Furniture may move or be added only where it does not block a cone the puzzle uses: low things
  (benches, bins under 1 m) anywhere; anything that blocks sight, ask.

## Free to dress

The timetable board and clock, posters and lit signs on the back wall (lit shapes, not words: 4–5
px text does not read), the tunnel mouths, the platform's edge markings and tactile line, the
stair's handrails and the light falling down it, benches, bins, a vending machine at the west
end, the ceiling's fluorescent tubes as light painted into the floor. The train itself is drawn
by the game from the timetable (agent A); its look is not the room's.

## Rules for every room

- **The 1 m cut**: everything in the play area is cut at 1 m (the front wall, pillars, kiosks,
  counters), its cut top drawn light like a section. Only the back wall, the end walls, stairs
  and what stands against the back wall go up to 2.4 m (the section's ceiling). At 60° a 2.4 m
  thing hides 1.4 m of floor behind it, and the thief with it.
- **Triangle budget**: the room, everything placed in it, 2,500 triangles (DESIGN.md, Budgets).
  The greybox is about 260.
- **Recipes**: Asset Kit recipes in this folder (any subfolder), names starting `r1_`, built in
  the room's frame and placed at yaw 0, verification required in depth mode (`"verification":
  {"required": true, "depth": true, "perspective": true}`). Point lights are welcome
  (`lighting.lights`). Every placement needs `collision`: a companion recipe with the floors and
  the walls (walls without tops, as `greybox/r1_shell_col.asset.json`), or `self` for small
  things, or `none`.
- **Placements**: list them in `arrival.placements.json` (the same format: `id` with the `r1_`
  prefix, `asset`, `position` in the room's frame, `collision`). Tell the level lead which folders
  your recipes are in, for `make_level1.py`'s `ROOMS`.
- **Checks**: `make B=build-mine build-mine/carts/afterhours.mei` builds the level with the World
  Checker; `python3 carts/afterhours/levels/level1/solutions.py --check` plays the room's solution on
  the model; the cart's scenario for the room (agent A's `tests/check.sh`) plays the tape.
