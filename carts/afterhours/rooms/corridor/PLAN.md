# The department store (stage 3), room 2: the staff corridor (floor plan)

The store's hub (`levels/store/ROUTE.md`), crossed three times. The back of house behind the cinema
and the store on the eighth floor: a wide service corridor, fluorescent tubes, roll cages of stock
parked down its west half, the security office in the middle of its front wall with a window onto
the corridor, pallets along the back. Three doors: from the cinema (west), a **blue** staff door in
the back wall up to the projection booth, and the staff stair down to the shop floor (east). A
porter walks round the roll cages; the guard in the office looks out of his window from side to
side; a camera over the stair door watches the east end. A column stands in the back lane straight
out from the office window: its shadow is the room's secret.

The greybox is `make_corridor.py` (it writes `greybox/`, `corridor.placements.json` and
`corridor.play.json`). The dressed room replaces the greybox recipes and the placements file;
the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres.

```
 z 3.75 ┌──────────── back wall (2.4 m) ──[BLUE]─────────────────────────────────────────┐
   3.5  │ ◆ porter NW       x −6.6 … −5.4 ◆ porter NE    ▪ column        pallets (low)  │
        │ (−10.2, 2.3)      (to the booth)  (−3.2, 2.3)  (1.15…1.85,     x 6 … 9.5      ▯ stair
        │        ┌── roll cages ──┐                     1.85…2.55)                     ║ z 1.4 … 2.6
        │        │ x −9 … −5      │                ┌═══ window (glass) ═══┬─────┐       │
        │        │ z −1 … 0.8     │                │  x −0.85 … 2.5        │wall │       │
  door ▯│        └────────────────┘          office│     ◆ guard (1.5,−1.6)│     │       │
 z −2.6 ║ ◆ porter SW                    ◆ porter │  desk                  │     │  ● camera (12.3, −3.3)
 … −1.4 │ (−10.2, −2.4)                  SE      └───────────────────────┴─────┘       │
  −3.5  ├──────────────────────── front wall, cut at 1 m ──────────────────────────────┤
 −3.75  └ x −12.75 … 12.75 ────────────────────────────────────────────────────────────┘
```

| Thing | Where | Size | In play |
|---|---|---|---|
| Floor | x −12.5 … 12.5, z −3.5 … 3.5 | 25 × 7 | |
| Back wall, end walls | z 3.5 … 3.75; x ±12.5 … ±12.75 | 2.4 high | walls; doorways: west z −2.6 … −1.4, back x −6.6 … −5.4 (blue), east z 1.4 … 2.6 |
| Front wall | z −3.75 … −3.5 | **cut at 1 m** | wall |
| Roll cages | x −9.0 … −5.0, z −1.0 … 0.8 | 1.8 high (cut at 1 m) | block cones; the porter's round goes round them |
| Security office | x −1.0 … 4.0, z −3.5 … 0.2, walls 0.15 | **cut at 1 m** | its west and east walls block cones; its north side: glass from x −0.85 to 2.5 (cones pass), a wall from 2.5 to 3.85 (blocks); no door on the corridor side |
| Desk | x −0.5 … 3.5, z −3.5 … −2.8 | 0.75 | |
| Column | x 1.15 … 1.85, z 1.85 … 2.55 | to the ceiling (cut at 1 m) | blocks cones: the office guard's shadow |
| Pallets | x 6.0 … 9.5, z 2.6 … 3.5 | 0.9 | stop the thief, cones pass over |
| Cinema door | west, `sc_door_cinema` | 1.2 wide | to `cn_door_corridor`; spawn (−11.6, −2.0) facing east |
| Blue staff door | back wall, `sc_door_booth`, **card blue** | 1.2 wide | to `pb_door_corridor`; spawn (−6.0, 2.6) facing south; A draws its blue leaf |
| Stair door | east, `sc_door_shop` | 1.2 wide | to `sf_door_corridor`; spawn (11.6, 2.0) facing west |
| Porter (patrol) | starts (−7.0, −2.4) | 1.1 m/s, 4.5 m, 60°, head 220°/s | (−3.2, −2.4) → (−3.2, 2.3) → west along the back → (−10.2, 2.3) → (−10.2, −2.4) → round the cages (about 21 s) |
| Office guard (posted) | (1.5, −1.6), inside the office | 6 m, 60° | looks −40 (north-west) 1.5 s, turns to 40 (north-east) over 2.5 s, holds 1.5 s, turns back: 480 ticks a cycle |
| Stair camera | (12.3, −3.3), 2.3 up | 8 m, 40° | sweeps 280 … 328 (holds 1.5 s, turns 2.5 s), 360 ticks into its cycle at clock 0; never sees the stair door's spawn |

The solutions (`SOLUTION_S2_LEG_1`, `_3`, `_5`):

- **Cinema door to the stair**: behind the porter along the front of the cages; up the west side
  of the office when he has turned the far corner; into the column's shadow while the office
  guard looks east; on to the stair while he looks west and the camera looks away. About 21 s.
- **Stair to the blue door**: along the east end to the pallets' corner while he looks west;
  into the column's shadow as he turns west again; out of it while he looks east, round the
  office's west side, behind the porter to the blue door, which opens. About 15 s.
- **Blue door to the stair**: out of the door behind the office guard's eastward turn and into
  the column's shadow; to the pallets' corner while he looks west; on to the stair when the
  camera looks away. About 21 s.

## Must stay

- The office where it is: its window glass and only as wide as it is (x −0.85 … 2.5), its side
  walls and the wall east of the window blocking cones. The office guard where he is.
- The column where it is, straight out from the window, and nothing else in the back lane
  between the office and the back wall that blocks cones.
- The roll cages as one block the porter walks round, with 1.7 m or more round them.
- The three doorways, their spawns, and the pallets low.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The office (monitors showing the floors, a key cabinet, the guard's thermos, a lit window), the
roll cages' stock, fluorescent tubes (some flickering), fire doors and hose reels on the walls,
floor markings, a staff notice board (shapes, not words), the stair beyond the east door, the
booth's stair beyond the blue door.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `sc_` and its
placements in `corridor.placements.json`.
