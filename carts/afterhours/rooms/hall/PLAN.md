# The tower, the lift hall on the sixth floor (floor plan)

The tower's second room, and its sixth: the thief crosses it twice (`levels/tower/ROUTE.md`). The
building's core stands in the middle (the lifts on its south face, the fire stair in its west
face; the same core, in the same place, is on the ninth floor and the roof). A corridor runs
round it, split by the securities house's glass screens into two halves that no door joins:

- **The lift lobby** in front: the lifts from the lobby open here, the night guard walks it, and
  the securities house's glass doors lead west onto the trading floor. Leg 2: from the lifts to
  the trading floor.
- **The back of house** round the core: the west corridor (with the fire stair's door), the back
  corridor behind the core, and the east end with the cleaners' boxes and the goods lift down to
  the loading bay. Leg 6: from the fire stair, down from the roof, to the goods lift, the
  stage's end.

The glass stops the thief and nobody's eyes: from the lift lobby the player sees the back of
house he will cross at the end, and each half's watcher sees into the other. The layout sheet is
`levels/tower/sketch.png`. The greybox is `make_hall.py` (it writes `greybox/`,
`hall.placements.json` and `hall.play.json`). The dressed room replaces the greybox recipes and
the placements file; the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. Inner faces of the walls: x -11 ... 11, z -4.5 ... 4.5 (22.5 x 9.5 outside;
the camera pans across).

| Thing | Where | Size | In play |
|---|---|---|---|
| Core (lifts, fire stair, risers) | x -5 ... 3, z 0.2 ... 3 | full height (cut at 1 m) | wall: blocks the thief and cones |
| Back corridor | between the core and the back wall, z 3 ... 4.5 | 1.5 wide | the way round behind the core |
| Glass screen, west | x -11 ... -5, z 0.05 ... 0.2 (from the west wall to the core) | full height glass | stops the thief, **not** cones |
| Glass screen, east | x 3 ... 3.15, z -4.5 ... 0.2 (from the front wall to the core) | full height glass | stops the thief, **not** cones |
| Lifts | the core's south face, x -4.4 ... -0.2; the one he comes out of at x -2.2 | doors (marks on the floor in front) | a way in only: spawn (-2.2, -0.9), facing the camera |
| Glass doors to the trading floor | west wall, z -3.6 ... -2.4 | doorway | door `lh_door_trading` |
| Fire stair door | the core's west face, z 1.1 ... 2.3, at x -5 | doorway in the core | door `lh_door_stair` (to the roof); spawn (-6.2, 1.7) facing west |
| Goods lift | east wall, z -3.6 ... -2.4 | doorway | door `lh_door_goods`: the stage's end |
| Planter | x -4.5 ... -3.5, z -2 ... -0.7 | 1.2 high | blocks cones: the thief's cover outside the lift |
| Reception desk | x -10.4 ... -8.6, z -4.5 ... -3.9 | 1.0 (low) | stops the thief, cones pass |
| Sofa | x -0.2 ... 1.8, z -4.5 ... -3.9 | 0.6 (low) | stops the thief, cones pass |
| Cleaners' boxes | x 6.6 ... 8, z -1.4 ... 0 | 1.6 | blocks cones |
| Cleaner's trolley | x 6.4 ... 7.6, z 2.4 ... 3 | 1.0 (low) | stops the thief, cones pass |
| Night guard (patrol) | the lift lobby, z -2.2, x -8.6 ... 1.6 | 0.9 m/s, 6 m, 60 degrees | at the west end looks up the west corridor through the glass (10) 2 s; at the east end looks east through the glass at the back of house (90) 2 s |
| Cleaner (patrol) | round the boxes: (9.6, 1.4) → (9.6, -2.8) → (5, -2.8) → (5, 1.4) | 0.8 m/s, 5 m, 60 degrees | waits 1.5 s at (9.6, 1.4) looking down the east end (180) |

The solutions (`levels/tower/solutions.py`): leg 2 (`SOLUTION_TOWER_LEG_1`), out of the lift
behind the planter while the night guard comes east, then west behind him to the glass doors,
about 12 s. Leg 6 (`SOLUTION_TOWER_LEG_5`), from the fire stair up the west corridor and along
behind the core while the night guard walks away east, then, when the cleaner has turned west
along the front of his round, along the back and down the east end behind him to the goods
lift, about 14 s. The dash (agent G's) is never needed.

## Must stay

- The core where it is (x -5 ... 3, z 0.2 ... 3), solid to the ceiling: it is the same core as
  on the ninth floor and the roof. The back corridor behind it clear (1.5 m).
- The two glass screens closed from wall to core, see-through (glass or open grilles: nothing on
  them that blocks sight below 2 m). No door or gap between the two halves.
- The planter, the boxes, the doorways, the spawns and the lifts' face where they are; the
  lift lobby's front strip (z -4.5 ... -2.8) and the east end's strip (x 9.9 ... 11) clear.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The bubble's lift lobby: stone, brass, the lifts' floor indicators (no 9), a directory board (no
ninth floor), the securities house's name on the glass, the reception's lamp. Behind the glass:
the cleaners' half-lit corridor, the goods lift's battered doors, mop buckets, the fire stair's
door wedged open with folded cardboard.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room": the 1 m cut, doorways open and framed with a
way on beyond, 2,500 triangles, recipes verified in depth mode with collision companions,
placements in the room's `hall.placements.json` (never overwritten by `make_hall.py`), this
room's prefix `lh_`, the recipe folders reported for `levels/tower/make_tower.py`'s `ROOMS`.
