# Stage 2, room 3: the shop floor (floor plan)

Stage 2's fourth room (`levels/level2/ROUTE.md`), visited twice. A department store's floor at
night (watches, accessories, a few mannequins), the escalators stopped in their well in the
middle, glass counters lit low. The staff stair from the corridor comes in at the west end; the
service lift down to the food hall is in the back wall at the east end, behind a **red** staff
door. The **blue card** lies on the floor by the watch counter at the front of the east end. A
night guard walks a long round of the floor; a camera high in the back corner past the lift
sweeps between the lift and the east end.

The greybox is `make_shopfloor.py` (it writes `greybox/`, `shopfloor.placements.json` and
`shopfloor.play.json`). The dressed room replaces the greybox recipes and the placements file;
the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 5.0  ┌──────────────────── back wall (2.4 m) ─────────────────[RED lift]──────● camera
   4.75 │ ◆ night NW (−3.6, 3.4)               ▪ mannequin (5, 4)  x 8.4 … 9.8   (11.5, 4.6)
 stair ▯│                                            ◆ night NE (10.6, 3.4)                │
z 1.6 … ║ ┌counter┐                                  ┌counter┐                              │
   2.8  │ └───────┘ x −9…−6, z 1…1.7  ┌─ escalator ─┐ └───────┘ x 5…8.4                     │
        │       ▪ mannequin (−5.2, 0) │ well (2.4 m │                     ▪ mannequin (10, −0.5)
        │ ┌counter┐                   │  … cut 1 m) │ ┌counter┐                              │
        │ └───────┘ z −2.6 … −1.9     └─────────────┘ └───────┘                              │
        │ ◆ night SW (−3.6, −3.3)                           ◆ night SE (10.6, −3.3)  ▬ blue card (9.6, −3.9)
  −4.75 ├────────────────── front wall, cut at 1 m ─────────── watch counter (glass) ────────┤
  −5.0  └ x −12.25 … 12.25 ──────────────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −12 … 12, z −4.75 … 4.75 | 24 × 9.5 | |
| Back wall, end walls | z 4.75 … 5.0; x ±12 … ±12.25 | 2.4 high | walls; doorways: west z 1.6 … 2.8 (the stair), back x 8.4 … 9.8 (the lift, red) |
| Front wall | z −5.0 … −4.75 | **cut at 1 m** | wall |
| Escalator well | x −2.0 … 2.0, z −1.2 … 1.4 | cut at 1 m | blocks cones and the thief (the escalators' sides) |
| Glass counters | x −9 … −6 and 5 … 8.4, at z −2.6 … −1.9 and 1.0 … 1.7 | 0.95 | stop the thief, cones pass |
| Watch counter | x 8.6 … 11.0, z −4.75 … −4.3 | 0.95 | stops the thief, cones pass |
| Mannequins | (−5.2, 0), (5.0, 4.0), (10.0, −0.5), on plinths 0.6 square | tall (cut at 1 m) | block cones: the one at (5, 4) shades the back lane from the camera |
| Blue card | (9.6, −3.9) | | `sf_card_blue`: drawn by A |
| Stair door | west, `sf_door_corridor` | 1.2 wide | to `sc_door_shop`; spawn (−11.1, 2.2) facing east |
| Lift door | back wall, `sf_door_lift`, **card red** | 1.4 wide | to `fh_door_lift`; spawn (9.1, 3.9) facing south; A draws its red leaf |
| Night guard (patrol) | starts (−3.6, 0) | 1.1 m/s, 5 m, 60°, head 220°/s | (−3.6, 3.4) → east along the back past the lift → (10.6, 3.4) looks south 0.5 s → down the east end → (10.6, −3.3) looks west along the front 1.5 s → (−3.6, −3.3) → round again (about 40 s) |
| Lift camera | (11.5, 4.6), 2.3 up | 9 m, 40° | sweeps 200 (the east end, the card at its far edge) … 260 (the back lane to the lift): holds 1.5 s, turns 2 s |

The solutions:

- **The blue card** (`SOLUTION_S2_LEG_2`): down the west end and along the front while the night
  guard is on the back; at the watch counter's end, in for the card when the camera has swung to
  the lift, and back the way he came before the guard comes down the east end. About 29 s.
- **The lift** (`SOLUTION_S2_LEG_6`): behind the night guard along the back; when he is down the
  east end, past the mannequin as the camera swings back from the lift, to the red door, which
  opens. About 23 s.

## Must stay

- The escalator well where it is, blocking cones; the counters glass and low.
- The three mannequins where they are, blocking cones (the one at (5, 4) above all).
- The blue card's place and the watch counter beside it; the camera's corner.
- The doorways and their spawns; the front aisle (z −4.3 … −2.6) and the back lane (z 1.7 …
  4.75) free of anything that blocks cones, but for the mannequin at (5, 4).
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The counters' contents (watches lit in the cases, scarves, handbags), the escalators in their
well (stopped, their handrails), shop signs as shapes and colours, the floor's pattern, spot
lights, the lift's doors and call panel beyond the red door, the staff stair's landing.

## Rules for every room

As `levels/level2/ROUTE.md`, "Rules for every room", with this room's prefix `sf_` and its
placements in `shopfloor.placements.json`.
