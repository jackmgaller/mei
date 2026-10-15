# The shop floor (7F): dressing notes

A department store's accessories and watches floor after closing, dressed on the level lead's
plan (`PLAN.md`). The counters glow low under their glass (scarves and leather goods at the west
end on a wine carpet, watches on navy velvet at the east on a dove-grey one); the three
mannequins stand in warm spots; cream marble runs round them, cut by the escalator well, where two
stopped escalators go down past glass balustrades to 6F, lit blue from below. The staff stair's
light comes in green-white at the west door; a red lamp marks the staff door to the lift, and the
camera's red lamp is in the corner past it. On the cut front, the store's curtain wall in section:
dark glass with the city's lights in it.

## Signature props (once in stage 2)

- **The escalator well** with its two stopped escalators down to the floor below, glass
  balustrades and black handrails.
- **The mannequins**: a long wine dress, a camel coat, a navy suit, each cut at 1 m with its cut
  drawn pale.
- **Glass counters lit from inside**: watches on velvet, folded silk scarves and small leather
  goods; the watch counter at the front.
- **Handbags on lit shelves** along the back wall; the watch house's dial panel; a low table of
  folded knits.
- **The curtain wall in section** on the front, with the city in its glass.

## What stays as the plan says

`shopfloor.play.json` is untouched. The well (x −2 … 2, z −1.2 … 1.4) is a hole in the floor with
its balustrade cut at 1 m; the counters (0.95 m: a 0.6 m body, glass to 0.95) and the watch
counter are where they were; the mannequins stand on 0.6 m plinths where they were; the card's
place is clear. Nothing new is in the front aisle (z −4.3 … −2.6) or the back lane (z 1.7 …
4.75) but the bag shelves against the back wall (0.32 m deep, to z 4.43, out of the solution's
lane at z 3.6) and the mannequin at (5, 4). The one new prop on the floor, the knits table
(x 2.6 … 3.9, z −0.75 … 0.35, 0.72 m), is off the guard's round and every leg's path. The
doorways are open: beyond the west one, the staff stair's landing and its first steps up; beyond
the red one, the lift's vestibule, its doors and a lit call panel.

## How it is made

`dress_shopfloor.py` writes the recipes, `art/` and `shopfloor.placements.json`
(`--no-placements` leaves the placements alone). It imports `../passage/diorama.py` (the shared
recipe pieces, the kit's light formula on painted surfaces, painting, and now floors with holes
and walls with doorways, mapped by hand UVs onto their painted textures). Captured by
`../passage/capture.py shopfloor --build-dir build-ah-R2 [--verify]`, which also draws stand-ins
for what agent A draws (the card, the red leaf).

| Recipe | Triangles | What |
|---|---|---|
| `sf_floor` | 830 | the painted floor (six textures, the well cut out) and back wall, the walls and lintels, the front's face, the shelves and bags, the mannequins, the table, the stair landing and the lift vestibule; 240 of its triangles are light refinement (capped at 240) |
| `sf_escalators` | 498 | the well: its walls down to 6F, 6F's floor, the two escalators, their glass and rails, the balustrade (corners only: no light refines the glass) |
| `sf_counters` | 228 | the five counters, their trays and glass (corners only) |
| **room** | **1,556** | of the 2,500 allowed |
| `sf_floor_col` | 122 | collision: the floor, the walls without tops, the well, the counters, the table, the plinths |

Placements: `sf_floor` (collision `sf_floor_col`), `sf_escalators` and `sf_counters` (collision
`none`: both are in `sf_floor_col`). All pass the Asset Checker in depth mode. Textures:
175,119 bytes of VRAM; the eight 8-bit paintings share one 8-bit palette.

**Light**: 15 lights, one list (`room_lights()`): five counters (inside, under the glass), three
spots on the mannequins (soft shadows), a night fill, the red staff-door lamp, the camera's lamp,
the staff stair (soft shadows through its doorway), two shelf lights, the well's light from below.

## Costs (`shots/numbers.json`), the game's camera, depth mode

| View (pan x) | Room alone: drawn / CPU / GPU | With the thief, the guard, two cones and A's things |
|---|---|---|
| west (−5.65) | 879 / 179,457 / 335,978 | 1,066 / 217,030 / 347,946 |
| middle (0) | 877 / 178,091 / 337,780 | 1,065 / 215,804 / 367,021 |
| east (+5.65) | 853 / 175,459 / 326,934 | 1,035 / 212,636 / 361,989 |

About 18 % of the CPU and 17 % of the GPU for the room. In stage 2's world, built privately with
these placements: cell 1,556 triangles, stand-in 498; the World Checker 0 hard failures, 0 over
thresholds. `levels/level2/solutions.py --check` clears legs 2 and 6 (the camera still 0.44 m
off at its nearest: nothing here touches play), and scenario 63 plays all eight legs in the cart
on that world, every frame within the budgets.

## Shots

- `shopfloor_60.png`: the three views of the pan (x2); `shopfloor_60_K.png` and `_x3`: each,
  the thief waiting on the front aisle at (7, −3.7), the night guard on the back, the camera
  looking at the lift.
- `shopfloor_game.png`: the cart itself (scenario 63 at tick 3,300, leg 2) on the dressed world.

## What fought me

- **The back wall is mostly off the picture.** At 10 m deep, the floor's back edge sits on line
  16 and the wall shows to about 1.3 m: the shelves' lower bags show, the dial panel only its
  bottom. The floor carries the room.
- **The night was too dark.** The first pass, lit only by the cases and the spots, read as a
  black floor; a stronger, greyer night fill and brighter spots fixed it.
- **Repeated dial shapes read as the digit 8** on the watch trays; the watches are now small
  faces with straps.
- **Flush faces** where the stair's landing met its wall and the escalators met the well's wall,
  and the vestibule's floor met its walls: opened or moved by 1 cm.

## For the level lead

`make_level2.py`'s `ROOMS` entry for the shop floor: asset folder **`rooms/shopfloor`** (no name
is also in `greybox/`). `make_shopfloor.py` was not rerun.
