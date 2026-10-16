# The tower, the ninth floor (floor plan)

The tower's fourth leg (`levels/tower/ROUTE.md`): the floor the directory leaves out, the
chairman's own and undeclared, the assessor's find. The lifts skip it and the core's doors on
this floor are walled up. The thief comes up the securities house's service stair from the back
office on the sixth, into the floor's north-west corner, and leaves by the chairman's private
stair up to his helipad, in the chairman's office east of the core. A boardroom walled in glass
stands in front of the core; a guard goes round it and stops behind it for a long look through
the glass at the front. A camera in the chairman's office watches his stair door. The coat
cupboard by the service stair is somewhere to hide.

The layout sheet is `levels/tower/sketch.png`. The greybox is `make_ninth.py` (it writes
`greybox/`, `ninth.placements.json` and `ninth.play.json`). The dressed room replaces the greybox
recipes and the placements file; the play file is the level lead's.

## The plan

The room's frame: x right on the screen, z away from the camera, the floor y = 0, the origin in
its middle. Metres. Inner faces of the walls: x -8 ... 8, z -4.25 ... 4.25 (16.5 x 9 outside).

| Thing | Where | Size | In play |
|---|---|---|---|
| Service stair door | back wall, x -7.4 ... -6.2 | doorway | door `nf_door_stair` (down to the trading floor); spawn (-6.8, 3.4) facing the camera |
| Private stair door | east wall, z 2.6 ... 3.8, inside the chairman's office | doorway | door `nf_door_up` (up to the roof) |
| Core | x -5 ... 3, z 0.4 ... 4.25 (to the back wall) | full height (cut at 1 m) | wall; its lift doors walled up on this floor |
| Coat cupboard | west wall, x -8 ... -7.1, z -1 ... 0.2, its sides 0.2 thick to 2 m | hiding place | A inside: unseen |
| Boardroom | glass walls x -3.4 ... 1.6, z -3.1 ... -0.8 (no door) | full height glass | stops the thief, **not** cones |
| Boardroom table | x -2.4 ... 0.6, z -2.4 ... -1.5 | 0.75 | inside the boardroom |
| Chairman's office wall | z 0.65 ... 0.8 from the core (x 3) to the east wall, its doorway at x 5 ... 6.2 | full height | wall |
| Chairman's desk | x 4.6 ... 6.2, z 2 ... 2.6 | 0.75 (low) | stops the thief, cones pass |
| Crated paintings | x 4 ... 5.4, z -3.4 ... -2.2; x 6.2 ... 7.4, z -1.4 ... -0.4 | 1.8 | block cones |
| Guard (patrol) | round the boardroom: (-1, -0.2) → (-4.3, -0.2) → (-4.3, -3.7) → (2.6, -3.7) → (2.6, -0.2) | 1.0 m/s, 6 m, 60 degrees | starts behind the boardroom looking through it at the front (180) 2 s, and stops there each round |
| Office camera | (7.7, 1.0), on the office wall by the doorway, 2.3 up | 6 m, 30 degrees | looks -20 (along the office) 2 s, turns over 2 s to 40 (at the stair door), 2 s, back (an 8 s cycle) |

The solution (`SOLUTION_TOWER_LEG_3`): down the west end into the coat cupboard and hide (A)
before the guard comes along behind the boardroom and down the west side; out when he has turned
east along the front, east along behind the boardroom (its glass hides nothing: he must be
walking away), through the office's doorway before he comes up the east side, to the office's
back west corner; when the camera has turned past the stair door into the corner (40) and holds,
across the office to the private stair. About 22 s. The dash (agent G's) is never needed.

## Must stay

- The core solid to the ceiling where it is (the same core as on the sixth and the roof); its
  walled-up lift doors may show as such.
- The coat cupboard (a hiding place: the thief inside it, A); its sides.
- The boardroom's glass closed and see-through below 2 m (blinds up).
- The office wall and its doorway, the desk, the camera's place, the stair doors.
- The corridor between the core and the boardroom (z -0.8 ... 0.4) and the front strip clear.
- The front wall cut at 1 m; the walls where they are (the wall map is written from them).

## Free to dress

The chairman's floor of the bubble: deep carpet, wood panelling, the paintings bought at auction
(crated, and one or two hung), a golf bag, a model of the company's next tower, the boardroom's
long table and leather chairs, the chairman's desk with its view, his private stair's door in
the panelling. Nothing that names a real company or a real painting.

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room", with this room's prefix `nf_` and its
placements in `ninth.placements.json`; recipe folders listed for `levels/tower/make_tower.py`'s
`ROOMS`.
