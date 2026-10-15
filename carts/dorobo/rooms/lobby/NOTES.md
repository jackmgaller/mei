# Room 4, the lobby: dressing notes

The tower's lobby at night, dressed on the level lead's plan (`PLAN.md`). The street's sodium
lamps stand outside the glass front: their orange light falls in across the polished black
granite, striped by the mullions' shadows, and gives out by the desk. Behind it the lobby is
dark blue, lit only by its own small lights: the desk's logo and its under-counter glow, the
directory board, two security downlights (one over the escalator's foot), the lifts' indicators,
the escalator's green comb light, and the passage's stair light at the door.

## Signature props (so that rooms 1 and 2 do not repeat them)

- **The planters' palms** (the level's only plants): fronds seen from above, cut under 1 m.
- **The reception desk**: a marble counter, the tower's mark (a wave over three bars) lit on its
  front, a signing-in book, a desk telephone, a brass bell, the receptionist's chair. No desk lamp
  or CRT (room 2's office has them).
- **The stopped escalator**: grooved treads, stainless sides, glass balustrades cut at the
  section's ceiling, black handrails; its comb light green.
- **The lifts** in the east wall (brushed steel, lit indicators and call button).
- **A low black leather sofa** by the west wall.
- **The directory board** on the back wall (rows of coloured blocks, a lit header) and a brass
  plaque with the tower's mark; a brass rosette in the floor before the desk.
- **The street's light through the glass front**, painted on the floor with the mullions'
  shadows, and the front itself: a granite sill, glass and posts cut at 1 m, the doors' push bars.

No desk lamp, CRT monitor, clock, vending machine or bench here.

## What stays as the plan says

The walls, the door, the lifts' place and the wall map are the plan's (`lobby.play.json` is
untouched). The escalator keeps the greybox's profile (12 steps of 0.19 m, x 1 … 7) and its
balustrade at z 3.5 … 3.63; its foot (the exit) is open. The desk is where it was and opaque
(0.97 m); the planters are 1 m square where they were (0.55 m boxes, palms to 0.95 m). Nothing
new stands on either guard's line, between the desk and the escalator's foot, or on the thief's
route: the chair is behind the desk (x −0.85 … −0.35), the sofa against the west wall
(x −6.97 … −6.15, z −2.35 … −0.55). Everything in the play area is under 1 m.

## How it is made

`dress_lobby.py` writes the recipes, the textures in `art/` and `lobby.placements.json`
(`--no-placements` leaves the placements alone). It imports `../passage/diorama.py` (the shared
recipe pieces, light formula and painting) and is captured by `../passage/capture.py lobby`.

| Recipe | Triangles | Vertices | What |
|---|---|---|---|
| `r4_lobby` | 557 | 413 | the painted floor (four quarters) and back wall, the side walls and lifts, the desk, the planters and palms, the sofa; 259 of its triangles are light refinement (capped at 260, by choice) |
| `r4_escalator` | 218 | 136 | the escalator: its own recipe, lit at its corners only, so no light refines its glass |
| `r4_front` | 134 | 108 | the glass front cut at 1 m, for the same reason |
| **room** | **909** | | of the 2,500 allowed |
| `r4_lobby_col` | 164 | | collision: the floor, the walls without tops, the desk, the planters, the balustrade, the escalator's steps |

Placements: `r4_lobby` (collision `r4_lobby_col`), `r4_escalator` and `r4_front` (collision
`none`: the steps are in `r4_lobby_col`, the front is the wall's). All recipes pass the Asset
Checker in depth mode. Textures: 111,277 bytes of VRAM; the six 8-bit paintings share **one**
8-bit palette (30 in my build), quantised together as the passage's are.

**Light.** One list, `room_lights()`, 12 lights: the two sodium lamps (hard-edged shadows, radius
0.12), a blue sign across the street, a night fill, the desk's glow and its logo, the lifts, the
comb light, two downlights, the directory board, the passage's stair. The painting gives the
lamps the building's story: the glass from the sill to 2.4 m, the posts full height, the wall
above the glass, the desk, the planters and the palms' fronds (as small boxes, so their shadows
are dappled), the escalator. The floor adds the reflections of the lit things in the polished
granite.

## Costs (`shots/numbers.json`), the game's camera, depth mode

| View | Room alone: drawn / CPU / GPU | With the thief, two guards and their cones |
|---|---|---|
| the room (it fits: no pan in z) | 556 / 126,428 / 295,276 | 814 / 177,566 / 323,120 |

About 12.6 % of the CPU and 14.8 % of the GPU for the room. In the level's world (built privately
with these placements): the cell is 909 triangles, its stand-in 218; the World Checker reports 0
hard failures and 0 over thresholds in 81 views. The cart's 25 scenarios pass on that world, and
`levels/level1/solutions.py --check` clears the lobby on tick 1,180.

## Shots

- `lobby_60.png` (x2) and `lobby_60_0.png`, `_x3`: the game's framing, the thief stand-in behind
  the desk (2.2, −1.1), the west guard at the back of his walk looking north, the back guard at
  the west end of his looking west, their cones (4.5 m, 60°, 16 rays).
- `lobby_game.png`: the cart itself (scenario 44 at tick 700) on the dressed world.

## What fought me

- **The game's framing shows little of the back wall.** The floor's back edge sits on line 16,
  so the wall is cut about 1.3 m up: the directory board went down to 0.3–1.25 m to be seen, and
  the escalator's upper half is out of the picture. The lifts, in the east wall, are seen edge
  on; their light on the floor is what shows.
- **Street light needs shadows to read.** Without them the sodium light was a flat orange wash;
  with the posts and the wall above the glass as blockers it falls in stripes and stops by the
  desk, which is the look.
- **Nonplanar fronds.** A tilted quad, rounded to the kit's precision, failed the planarity test;
  each frond is two triangles.
- **Flush faces** at the sofa's arms, the chair, the newels; and a post at x 0 doubled with a door
  post (a duplicate face). Fixed by insetting and dropping the post.

## For the level lead

`make_level1.py`'s `ROOMS` entry for the lobby: asset folder **`rooms/lobby`**. `make_*.py` was
not rerun.
