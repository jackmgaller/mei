# The cinema: dressing notes

The auditorium after the last show. The film still runs to an empty house. The screen's cold light
falls across the rows and throws their shadows east, painted soft into the carpet. The
projector's beam runs high over the middle aisle from the window in the east wall: two additive
sheets, kept faint so the camera's cone reads through it. Also here:

- red carpet with a gold motif, plainer in the aisles;
- amber step lights at every row's end;
- the house lights left low at the corners and along the back aisle;
- warm sconces fanning up the pleated back wall, and green exit pictograms;
- velvet curtains at the screen's ends, cut at 1 m with their folds in the section;
- speakers behind the screen;
- popcorn in the back aisle the cleaner has not reached;
- the aquarium corridor's blue beyond the start door, and the staff corridor's light beyond the
  east door.

## Files (mine)

| File | What |
|---|---|
| `dress_cinema.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; with `--placements`, also `cinema.placements.json`. Imports `make_cinema.py` for its numbers only |
| `dressed/` | **The recipe folder for `make_level2.py`'s `ROOMS`**, instead of `rooms/cinema/greybox` |

Shared code is in `../corridor/s2dress.py`: the shell from the greybox description, and floors
and walls painted from the light list. That code builds on level 1's `../arrival/dresskit.py`.
Captures: `python3 carts/afterhours/rooms/corridor/capture.py cinema --verify`.

## Signature props (once in the stage)

- **Cinema seat rows**: 24 rows of red velvet, facing the screen.
- **The screen and its curtains.**
- **The projector's beam.**
- **Amber aisle step lights.**
- **Brass wall sconces.**
- **Spilt popcorn.**
- **The green exit pictogram** (also over the corridor's stair door: it is wayfinding).

## Numbers

| Recipe | Triangles |
|---|---|
| `cn_room`: shell, floor in 4 painted tiles, back wall in 2, screen, curtains, speakers, 24 rows, sconces, signs, port. Includes 69 triangles of light refinement (cap 260) | 715 |
| `cn_beam`: unlit, additive, collision `none` | 2 |
| **Room** (budget 2,500) | **717** |

- **Collision:** `cn_room_col` is `s2room.shell_nodes(ROOM, collision=True)`, the greybox's own,
  under a new name.
- **Asset Checker:** both recipes pass in depth mode.
- **VRAM:** 138,608 bytes of textures.
- **At 60°, room alone (pans west / middle / east):**

  | Pan | Triangles | CPU cycles | GPU cycles |
  |---|---|---|---|
  | west | 424 | 86,758 | 329,365 |
  | middle | 404 | 84,678 | 330,319 |
  | east | 394 | 83,702 | 301,090 |

- **At 60°, with stand-ins and three cones:** up to 690 triangles, 140,107 CPU and 378,168 GPU
  cycles.
- **In the cart (scenario 63, leg 0):** at most 677 triangles, 166,628 CPU and 382,929 GPU
  cycles.
- **Checks:** the World Checker passes. Leg 0 clears on the model. Scenarios 60–64 and all 32
  scenarios of `tests/check.sh`, plus the 7 front-end scenarios, pass on a private build of
  stage 2 with my three rooms dressed.

## For the level lead

- **`ROOMS`:** `rooms/cinema/dressed`. Until `ROOMS` changes, rerunning `make_level2.py` breaks
  the build.
- **The screen:** the wall map's screen spans z −3.2 … 3.6. The drawn screen spans z −2.8 … 3.2,
  and the curtains fill its 0.4 m ends, x −9.42 … −8.86. Both gaps behind it are clear.
- **Things the thief walks through** (none blocks a cone the plan uses):
  - the curtains, which reach 0.14 m east of the screen, inside the 0.3 m band his centre cannot
    reach;
  - the speakers behind the screen, x −9.62 … −9.3.

## What fought me

- **The beam** at first was a bright blue wedge over half the room and hid the cones. It is now
  dark additive sheets, narrower at the screen.
- **The carpet** was black between the rows until I added low house lights at the corners and
  along the back aisle.
- **Coplanar tops:** the curtains' and speakers' tops met the screen's at 1 m. The Asset Checker
  caught it, and the screen box now stops where the curtains begin.
