# The tower, the roof (floor plan)

The tower's fifth leg (`levels/tower/ROUTE.md`): the top of the office tower at night, the
city's lights all round below the parapet. Over the core stand the lift motor room and the fire
stair's house; the chairman's helipad is painted at the east end, with his private stair's house
beside it (bubble excess: a helicopter to the golf course). Water tanks, air-conditioning plant
and the lift shaft's skylight stand about. A searchlight on its mast at the motor room's front
sweeps a narrow beam slowly across the roof and back; everything standing on the roof casts a
shadow in it, and those shadows are the room's stepping stones. A guard walks the west end, past
the fire stair's door. The thief comes up the chairman's stair (east) and leaves by the fire
stair (in the motor room's west face), down the core to the sixth floor.

The layout sheet is `levels/tower/sketch.png` (the beam is drawn at several headings, cast
against what blocks it). The greybox is `make_roof.py` (it writes `greybox/`,
`roof.placements.json` and `roof.play.json`). The dressed room replaces the greybox recipes and
the placements file; the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. Inner faces of the parapets: x -11 ... 11, z -4.5 ... 4.5 (22.5 x 9.5
outside; the camera pans across).

| Thing | Where | Size | In play |
|---|---|---|---|
| Chairman's stair house door | east parapet's gap, z 2.4 ... 3.6 (the stair house beyond it) | doorway | door `rf_door_private` (down to the ninth); spawn (10.1, 3.0) facing west |
| Fire stair door | the motor room's west face, z 1.1 ... 2.3, at x -5 | doorway | door `rf_door_stair` (down to the sixth) |
| Motor room and fire stair house | x -5 ... 3, z 0.2 ... 4.5 (to the back parapet) | full height (cut at 1 m) | wall: its shadow holds the fire stair's door |
| Helipad | x 4.4 ... 9.4, z -3.4 ... 1.4 | painted | nothing in play |
| Water tanks | x 5.2 ... 6.8, z 2.4 ... 4; x -9.8 ... -8.2, z -1.2 ... 0.4 | tall (cut at 1 m) | block cones |
| Plant | x 1.4 ... 2.8, z -3 ... -1.6; x -6.9 ... -5, z -3.75 ... -2 | 1.6 | block cones: the two shadows the solution waits in |
| Skylight | x -2.6 ... -1.2, z -2.6 ... -1.8 | 1.2 | blocks cones |
| Searchlight (camera) | (-1, -0.1), on its mast at the motor room's front, 2.3 up | 12 m, **10 degrees** | looks 95 (east) 2/3 s, sweeps over 6 s to 265 (west), 2/3 s, back (a 13.3 s cycle) |
| Guard (patrol) | the west end, x -7, from (-7, 3.6) to (-7.2, -0.6) | 0.8 m/s, 5 m, 60 degrees | at the north end looks south (180) 2 s; at the south end looks north (0) 2.5 s |

The solution (`SOLUTION_TOWER_LEG_4`): when the beam has swept on west past the helipad, from the
stair house down to the east plant's shadow (3.2, -3.5); when it has swept back east past him,
along the front past the skylight to the west plant's shadow (-6.2, -4.15), ahead of the beam as
it comes round again; when the guard is walking away north and the beam is on its way back east,
round the plant and up to the fire stair in the motor room's shadow, behind the guard. About
29 s. Run straight across, the roof clears from about one start time in six. The dash (agent
G's) is never needed.

## Must stay

- The two plant units, the skylight, the tanks and the motor room where they are, blocking
  cones: their shadows are the room. Nothing new that blocks sight between them and the
  searchlight, and nothing tall near its mast.
- The front of the roof (z -4.5 ... -3.4) clear: the solution walks it under the parapet.
- The guard's walk clear (1 m either side of x -7), the doorways, the spawn and the fire stair.
- The front parapet cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The night: the city below the parapet on all sides (a backdrop beyond the cut front is welcome),
the helipad's H and its edge lights, a windsock, the chairman's stair house (smarter than the
fire stair's), the tanks' ladders and pipes, the plant's fans, puddles, the searchlight's beam
(light only, faint, so its narrow cone reads), aircraft warning lights on the motor room.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `rf_` and its
placements in `roof.placements.json`; recipe folders listed for `levels/tower/make_tower.py`'s
`ROOMS`.
