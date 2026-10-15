# The food hall (B1): dressing notes

The store's basement food hall after closing, dressed on the level lead's plan (`PLAN.md`). Its
four glass cases glow from inside (cakes, fruit, wagashi, wrapped gift boxes), each with its
price cards in a row; warm terrazzo with brown guide bands down the aisles; the shops along the
back wall shut behind their noren, their paper andon lamps still lit on the counters; the melon
counter at the east end, its melons each in a paulownia box under a warm lamp. The service lift's
car stands open and bright beyond its doorway at the west end of the back wall; the mall's light
comes in under the rolled-up shutter at the east door, under a green exit sign. On the cut front,
the basement's wall and the ground beside it in section.

## Signature props (once in stage 2)

- **The glass cases of food**, lit from inside: cakes, fruit, wagashi, gift boxes.
- **The melon counter**: melons in paulownia boxes, price cards.
- **Paper andon lamps** on the shops' counters along the back wall, and the shops' **noren**
  (on the wall's painting; at this framing only their lower edge shows).
- **A parked cleaner's cart** (yellow, a bucket and a mop) in the west end.
- **The service lift's padded car** (quilted blankets) open beyond the back doorway.

No mannequins, escalators or watch counters here (the shop floor has them).

## What stays as the plan says

`foodhall.play.json` is untouched. The four cases are where they were (0.95 m: a 0.6 m body,
glass to 0.95), the melon counter 0.82 m with its melons to 0.99 m, the columns 0.7 m square cut
at 1 m. The gift boxes are agent A's: the floor under them is plain, with room round each. The
back counters (0.5 m deep against the back wall, to z 4.25, 0.86 m, the andons to 1.3 m against
the wall) are off the cleaner's round (z 2.9) and the lift's spawn (the lift's doorway x −10.4 …
−9.0 is clear of them). The cart (x −11.9 … −11.25, z 2.6 … 3.5) is west of the solution's path
(x −9.7 … −10.5). The doorways are open; beyond the east one, the mall's floor and the shutter
rolled up in its box above the doorway (nothing across it below 1.94 m).

## How it is made

`dress_foodhall.py` writes the recipes, `art/` and `foodhall.placements.json` (`--no-placements`
leaves the placements alone), with `../passage/diorama.py`'s helpers. Captured by
`../passage/capture.py foodhall --build-dir build-ah-R2 [--verify]` (stand-ins for A's gift box
stacks and the cards).

| Recipe | Triangles | What |
|---|---|---|
| `fh_hall` | 1,183 | the painted floor (six textures) and back wall, the walls and lintels, the front's face, the columns, the back counters, andons and wares, the melon counter and melons, the cart, the lift car and the mall's floor; 237 of its triangles are light refinement (capped at 240) |
| `fh_cases` | 144 | the four cases, their trays and glass (corners only: no light refines the glass) |
| **room** | **1,327** | of the 2,500 allowed |
| `fh_hall_col` | 98 | collision: the floor, the walls without tops, the cases, the melon counter, the columns |

Placements: `fh_hall` (collision `fh_hall_col`) and `fh_cases` (collision `none`: they are in
`fh_hall_col`). Both pass the Asset Checker in depth mode. Textures: 175,775 bytes of VRAM; the
eight 8-bit paintings share one 8-bit palette.

**Light**: 13 lights, one list: the four cases (inside), the three andon rows, the melon lamp
(soft shadows), the mall through the shutter door and the lift car through its doorway (both
with soft shadows, so each door throws a wedge of light), a warm night fill, the camera's lamp,
the exit sign.

## Costs (`shots/numbers.json`), the game's camera, depth mode

| View (pan x) | Room alone: drawn / CPU / GPU | With the thief, three watchers, their cones and A's things |
|---|---|---|
| west (−5.65) | 720 / 164,998 / 305,422 | 1,023 / 225,485 / 345,106 |
| middle (0) | 713 / 164,468 / 321,163 | 1,009 / 224,327 / 366,911 |
| east (+5.65) | 710 / 164,025 / 305,293 | 1,011 / 224,344 / 355,697 |

About 16.5 % of the CPU and 16 % of the GPU for the room. In stage 2's world, built privately with
these placements: cell 1,327 triangles, stand-in 144; the World Checker 0 hard failures, 0 over
thresholds. `levels/level2/solutions.py --check` clears leg 7, and scenario 63 plays it (and the
other seven) in the cart on that world.

## Shots

- `foodhall_60.png`: the three views of the pan (x2); `foodhall_60_K.png` and `_x3`: each, the
  thief waiting by the west column at (−3, −3), the melon guard looking up the hall, the cleaner
  on the back, the camera.
- `foodhall_game.png`: the cart itself (scenario 63 at tick 9,800, leg 7) on the dressed world.

## What fought me

- **The cases' light in the floor was too strong**: painted as glossy reflections at first, each
  case had a white slab before it; they are a third as bright now and the case lights dimmer.
- **The back wall is mostly off the picture** (as on the shop floor): the noren, painted at
  1.55–2.25 m, show only at the top of the frame, so the andons on the counters carry the back.
- **Flush faces** where the lift car's floor met its walls: the floor box opened on its sides.

## For the level lead

`make_level2.py`'s `ROOMS` entry for the food hall: asset folder **`rooms/foodhall`**.
`make_foodhall.py` was not rerun.
