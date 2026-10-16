# The tower, the trading floor on the sixth floor (floor plan)

The tower's third leg (`levels/tower/ROUTE.md`): a securities house's trading floor at night,
the bubble's money room. Rows of dealers' desks with their screens dark, two columns, a meeting
room walled in glass against the front, and in the north-west corner the back office behind its
partition. The thief comes in by the glass doors from the lift hall (east) and leaves by the
door behind the trading floor: the back office's door to the house's own service stair, the one
way up to the ninth floor that the lifts skip. A guard walks the middle aisle; a camera in the
back office looks across it at the stair door and turns away to the window.

The layout sheet is `levels/tower/sketch.png`. The greybox is `make_trading.py` (it writes
`greybox/`, `trading.placements.json` and `trading.play.json`). The dressed room replaces the
greybox recipes and the placements file; the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. Inner faces of the walls: x -9 ... 9, z -4.5 ... 4.5 (18.5 x 9.5 outside).

| Thing | Where | Size | In play |
|---|---|---|---|
| Glass doors from the lift hall | east wall, z -3.6 ... -2.4 | doorway | door `tf_door_hall`; spawn (8.1, -3.0) facing west |
| Service stair door | back wall, x -8.6 ... -7.4, inside the back office | doorway | door `tf_door_stair` (up to the ninth) |
| Back office partition | south side z 0.9 ... 1.05 from x -9 to -5.4, with its doorway at x -7.9 ... -6.7; east side x -5.55 ... -5.4 from z 1.05 to the back wall | full height (cut at 1 m) | walls: block the thief and cones |
| Back office desk | x -7.4 ... -5.55, z 3.6 ... 4.5 | 0.75 (low) | stops the thief, cones pass |
| Meeting room | glass walls x -1.6 ... 2.5, z -4.5 ... -1.8 (against the front wall; no door) | full height glass | stops the thief, **not** cones |
| Meeting table | x -0.5 ... 1.4, z -3.6 ... -2.6 | 0.75 | inside the meeting room |
| Dealers' desks | x -4.6 ... -0.6, 0.4 ... 4.4 and 5.2 ... 8, z 1.8 ... 2.6; and x 4 ... 7.2, z -3.4 ... -2.6 | 0.9 (low) | stop the thief, cones pass |
| Columns | x -4.4 ... -3.7 and 3.5 ... 4.2, z -1.4 ... -0.7 | full height | block cones |
| Floor guard (patrol) | the middle aisle, z 0.4, x -4.6 ... 7.6 | 1.0 m/s, 6 m, 60 degrees | waits 1.5 s at each end: at the west end looking up the floor (0), at the east end looking down it (180) |
| Back office camera | (-5.75, 1.25), in the office's south-east corner, 2.3 up | 5 m, 30 degrees | looks 300 (across the office) 1.5 s, turns over 2 s to 350 (to the window), 1.5 s, back (a 7 s cycle) |

The solution (`SOLUTION_TOWER_LEG_2`): along the front to the meeting room's east side; when the
floor guard has walked off west past it, round the meeting room's north side behind him and down
to the front west corner, out of his sight while he looks up the floor; when he has turned back
east, up the west end into the back office's doorway (the camera never sees it), and when the
camera has turned to the window, across the office to the service stair. About 20 s. The dash
(agent G's) is never needed.

## Must stay

- The back office's partition and doorway, the desk, the camera's place, the stair door: the
  last step is timed against the camera across that office.
- The meeting room's glass closed and see-through below 2 m; the columns; the desks low (nothing
  on them that blocks sight: screens are dark and low).
- The front strip (z -4.5 ... -3.6) east of the meeting room, the strip north of it (z -1.8 ...
  -0.4) and the west end (x -9 ... -6.2) clear: the solution walks them.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The bubble's dealing room at night: banks of dark screens, the share board over the desks (stopped
at the crash's last close, or the bubble's peak), telephones, ashtrays, a Nikkei ticker on the
back wall, the meeting room's blinds half down (light only, not blocking), the back office's
filing cabinets and safe, the service stair's plain steel door.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `tf_` and its
placements in `trading.placements.json`; recipe folders listed for `levels/tower/make_tower.py`'s
`ROOMS`.
