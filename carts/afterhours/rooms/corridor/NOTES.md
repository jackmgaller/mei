# The staff corridor: dressing notes

The back of house on the eighth floor, crossed three times. It is dressed to reward being seen
often, and to show its secret.

**The secret, drawn in light.** The security office is lit cold by its tube and a bank of four
monitors (tilted back so their blue-green views of the floors face the camera). Its window throws
a pale trapezoid across the back lane. The column stands in it, and its shadow runs crisp to the
back wall: the place the guard never sees into. The trapezoid is painted from a paint-only light
at the window, which lights only beyond the glass (`zmin`). The office's own light is softer.

Also here:

- fluorescent tubes along both lanes, one failing: dim, with a green cast under it;
- grey sealed concrete in 3 m pours with saw cuts, scuffs where cages are swung round, and wheel
  tracks;
- yellow walkway lines, a hatched yellow-and-black bay round the roll cages, a stencilled arrow to
  the stair, a drain, and a blue line in front of the blue door;
- four roll cages with see-through wire sides (a cutout lattice) and cartons inside, the tallest
  cut by the section;
- three pallets of shrink-wrapped stock;
- the office's key cabinet in section (coloured tags on hooks), the guard's red thermos, a chair;
- on the back wall: a cork notice board of pinned papers, a red hose-reel cabinet, a big
  stencilled 8F (Figtree Bold), a bump rail, and the blue door's painted frame;
- beyond the blue doorway, the booth's stair climbing seven steps north in warm light;
- the cinema's dark red beyond the west door, and the stair's light and a green exit pictogram at
  the east door.

## Files (mine)

| File | What |
|---|---|
| `dress_corridor.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; with `--placements`, also `corridor.placements.json`. Imports `make_corridor.py` for its numbers only |
| `s2dress.py` | Shared by my three rooms. Builds the shell from the greybox description: walls round open doorways, lintels with a glow, reveals, sills, the front wall in a hatched section, floor tiles, back-wall chunks, and the way on beyond each doorway (a landing, or steps). Paints floors and walls from the light list. Builds on `../arrival/dresskit.py` |
| `capture.py` | `python3 carts/afterhours/rooms/corridor/capture.py cinema\|booth\|corridor --verify`: runs the Asset Checker, then draws the room at the game's camera, panned west, middle and east for a wide room, into `shots/` |
| `dressed/` | **The recipe folder for `make_level2.py`'s `ROOMS`**, instead of `rooms/corridor/greybox` |

`../arrival/dresskit.py` (my level 1 file) gained one optional light key, `zmin`. Level 1 is
unaffected.

## Signature props (once in the stage)

- **Roll cages of stock.**
- **The security office's monitor bank and key cabinet.**
- **The cork notice board.**
- **The red hose reel.**
- **The 8F stencil.**
- **Pallets of shrink-wrapped stock.**
- **Floor safety markings** (hatched bay, walkway lines).

## Numbers

| Recipe | Triangles |
|---|---|
| `sc_room`. Includes light refinement (cap 260) | 633 |
| `sc_glass`: the office window, unlit, collision `none` | 6 |
| **Room** (budget 2,500) | **639** |

- **Collision:** `sc_room_col` is the greybox's shell collision under a new name.
- **Asset Checker:** both recipes pass in depth mode.
- **VRAM:** 129,625 bytes of textures.
- **At 60°, room alone (pans west / middle / east):**

  | Pan | Triangles | CPU cycles | GPU cycles |
  |---|---|---|---|
  | west | 370 | 89,686 | 247,795 |
  | middle | 376 | 90,273 | 250,384 |
  | east | 365 | 88,973 | 244,243 |

- **At 60°, with stand-ins and three cones:** up to 648 triangles, 143,872 CPU and 290,847 GPU
  cycles.
- **In the cart (scenario 63, its three crossings):** at most 658 triangles, 213,200 CPU and
  297,059 GPU cycles.
- **Checks:** legs 1, 3 and 5 clear. The office guard's margin is still 0.41 m on the model. The
  wall map is untouched, and scenario 63 passes in the cart on the dressed build.

## For the level lead

- **`ROOMS`:** `rooms/corridor/dressed`.
- **Must stay:**
  - the window is glass from 0.85 to 1 m (`sc_glass`, x −0.85 … 2.5);
  - the office's side walls and the wall east of the window are cut at 1 m, with pale tops;
  - the column is cut at 1 m;
  - the cages stay one block;
  - the pallets are 0.7–0.9 m.

  The doorways have only a threshold in them, with the way on beyond. A's blue leaf draws in the
  back doorway.
- **Inside the office**, where nobody walks: the desk is 0.75 m; the monitors stand on it at
  0.8–0.98 m.

## What fought me

- **The window's light** was washed out by the back lane's tubes until I painted it as its own
  light at the glass. I also had to keep that light out of the office: it is the `zmin` key.
- **The monitors** faced away from the camera, and the first tilt was only grazing. Now they lie
  almost flat, and they read as screens from above.
- **Coplanar faces:** the cages' bases shared the wire sides' faces, and the chair's back shared
  its seat's sides.
