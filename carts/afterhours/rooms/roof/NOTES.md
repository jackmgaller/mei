# The roof: dressing notes

The top of the tower under the moon. The moon is a paint-only light high in the south-west, with
soft shadows. Everything standing on the roof throws a long blue shadow north-east, away from the
camera.

The roof's membrane is dark and wet:

- seams and drains;
- four puddles holding the sky and the red warning lights;
- a paver path from the chairman's stair house to his helipad.

**The helipad**: a green deck with a white edge, a yellow ring, a white H, and green edge lights
every metre. A red-and-white windsock stands by it.

**The lift motor room**, over the core, is cut at 1 m. Its section shows:

- three traction machines on their beds, with their sheaves over the hall's three shafts;
- the control cabinets with lit indicators;
- the fire stair's head at the west.

Its face is board-marked concrete with louvres. A warm bulkhead lamp lights the fire stair's
doorway, a recess in its west face.

**On the roof:**

- the searchlight's mast (A draws the lamp, as the camera, and the cone is its beam: I drew no
  beam);
- two panel water tanks on steel stands, their section showing the dark water inside;
- two air-conditioning units with their fans in section;
- the lift shaft's skylight on its kerb, glowing faintly from below;
- low parapets (1.15 m, with caps) and red warning lights on the back corners;
- the chairman's warm stair house beyond the east gap.

## Files (mine)

| File | What |
|---|---|
| `dress_roof.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; with `--placements`, `roof.placements.json`. Imports `make_roof.py` for its numbers only |
| `dressed/` | **The recipe folder for `make_tower.py`'s `ROOMS`**, in place of `rooms/roof/greybox` |

`../corridor/s2dress.py` gained a parapet option (`wall_nodes(height, top)`). The store's rooms
regenerate byte for byte as before.

## Signature props (once in the stage)

- **The helipad and its edge lights.**
- **The windsock.**
- **The motor room's machines.**
- **The panel water tanks.**
- **The air-conditioning units.**
- **The shaft's skylight.**
- **Red aircraft warning lights.**
- **The bulkhead lamp.**

## Numbers

| Recipe | Triangles |
|---|---|
| `rf_room`, refinement included (cap 220) | 240 |
| **Room** (of 2,500) | **240** |

Collision: `rf_room_col` is the greybox's own, under a new name.

- **Asset Checker:** the recipe passes in depth mode.
- **Textures:** 138,665 bytes, in slots 6 and 8–13 (the room's set is 13–8 and 6–0; slot 7
  untouched).
- **Room alone at 60°, panned west / middle / east:**

  | Pan | Triangles | CPU cycles | GPU cycles |
  |---|---|---|---|
  | west | 134 | 30,249 | 256,501 |
  | middle | 134 | 30,217 | 261,169 |
  | east | 132 | 30,033 | 250,355 |

- **With the stand-ins, the searchlight's cone and the guard's:** up to 312 triangles, 65,043 CPU
  and 281,266 GPU cycles.
- **In the cart** (scenario 91, leg 5): at most 341 triangles, 103,933 CPU and 288,167 GPU
  cycles. The greybox: 257, 91,134 and 211,549.

**Checks:**

- The World Checker passes.
- Leg 5 clears on the model, nearest 0.52 m to the searchlight's beam, as before.
- Scenarios 91 and 92 pass.

## For the level lead

- **`ROOMS`:** `rooms/roof/dressed`.
- **Parapets:** the back and end walls are drawn as 1.15 m parapets. The wall map's 2.4 m is
  unchanged: it only stops the thief there.
- **Kept where the plan has them:**
  - the plant, the skylight, the tanks and the motor room, all cut at 1 m;
  - the front strip and the guard's walk, which are clear.
- **New, and nothing that blocks sight:**
  - the windsock: a 0.035 m pole at (10.55, −2.1), off every leg's path;
  - the mast: 0.06 m;
  - the tanks' stands: under their tanks.

## What fought me

- **A city backdrop** beyond the back parapet never showed: the framing puts the floor's back
  edge at the picture's top, with no room above it for a backdrop. I took it out. The city's
  lights need the horizon planes, or the pull-back between rooms.
- **My searchlight lamp** sat where A draws the camera's body. I removed it and kept only the
  mast.
